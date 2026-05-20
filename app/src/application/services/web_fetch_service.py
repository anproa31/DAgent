"""Download remote tabular data files into the datasource store."""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import unquote, urlparse

import httpx
import pandas as pd

from ...core.config import get_settings
from ...models.datasource import DatasourceFileType
from .web_security import DATA_FILE_EXTENSIONS, UrlValidationResult, validate_fetch_url

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (compatible; DataAnalystAgent/1.0; +https://github.com/databao)"
)


@dataclass(frozen=True)
class FetchedFile:
    stored_path: str
    original_filename: str
    file_type: DatasourceFileType
    source_url: str
    content_type: str
    bytes_written: int


def _filename_from_url(url: str, content_type: str = "") -> str:
    path = unquote(urlparse(url).path)
    name = Path(path).name or "download"
    if "." not in name:
        if "json" in content_type:
            name += ".json"
        elif "csv" in content_type or "text/plain" in content_type:
            name += ".csv"
        elif "parquet" in content_type:
            name += ".parquet"
        elif "spreadsheet" in content_type or "excel" in content_type:
            name += ".xlsx"
        else:
            name += ".csv"
    return re.sub(r"[^\w.\-]+", "_", name)[:180]


def _detect_file_type(filename: str, content_type: str) -> DatasourceFileType:
    lower = filename.lower()
    if lower.endswith((".csv", ".tsv")):
        return DatasourceFileType.CSV
    if lower.endswith((".xlsx", ".xls")):
        return DatasourceFileType.EXCEL
    if lower.endswith(".parquet"):
        return DatasourceFileType.PARQUET
    if lower.endswith((".db", ".sqlite", ".sqlite3")):
        return DatasourceFileType.SQLITE
    if "json" in content_type or lower.endswith((".json", ".jsonl")):
        return DatasourceFileType.CSV  # converted below
    return DatasourceFileType.CSV


def _json_to_csv_path(raw_bytes: bytes, target_csv: str) -> None:
    text = raw_bytes.decode("utf-8", errors="replace")
    payload = json.loads(text)
    if isinstance(payload, dict):
        for key in ("data", "results", "records", "items", "rows"):
            if key in payload and isinstance(payload[key], list):
                payload = payload[key]
                break
        else:
            payload = [payload]
    if not isinstance(payload, list):
        payload = [payload]
    pd.DataFrame(payload).to_csv(target_csv, index=False)


async def fetch_url_to_file(
    url: str,
    *,
    max_bytes: int,
    timeout: float,
    allow_untrusted: bool = False,
    extra_trusted_suffixes: Optional[list[str]] = None,
    suggested_name: Optional[str] = None,
) -> Tuple[FetchedFile, UrlValidationResult]:
    validation = validate_fetch_url(
        url,
        allow_untrusted=allow_untrusted,
        extra_trusted_suffixes=extra_trusted_suffixes,
    )
    if not validation.ok:
        raise ValueError(validation.reason)

    settings = get_settings()
    datasource_id = str(uuid.uuid4())
    ds_dir = os.path.join(settings.files_dir, datasource_id)
    os.makedirs(ds_dir, exist_ok=True)

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").split(";")[0].lower()
            filename = suggested_name or _filename_from_url(url, content_type)
            temp_path = os.path.join(ds_dir, filename)

            total = 0
            chunks: list[bytes] = []
            async for chunk in response.aiter_bytes(1024 * 64):
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(f"Download exceeds size limit ({max_bytes} bytes)")
                chunks.append(chunk)
            raw = b"".join(chunks)

    file_type = _detect_file_type(filename, content_type)
    stored_path = temp_path

    if file_type == DatasourceFileType.CSV and (
        filename.lower().endswith((".json", ".jsonl")) or "json" in content_type
    ):
        stored_path = os.path.join(ds_dir, Path(filename).stem + ".csv")
        _json_to_csv_path(raw, stored_path)
        filename = Path(stored_path).name
        file_type = DatasourceFileType.CSV
    else:
        with open(stored_path, "wb") as out:
            out.write(raw)

    if not any(stored_path.lower().endswith(ext) for ext in DATA_FILE_EXTENSIONS):
        raise ValueError("Downloaded content is not a supported tabular file type")

    return (
        FetchedFile(
            stored_path=stored_path,
            original_filename=filename,
            file_type=file_type,
            source_url=url,
            content_type=content_type,
            bytes_written=os.path.getsize(stored_path),
        ),
        validation,
    )
