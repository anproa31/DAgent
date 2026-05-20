"""JSON file persistence for the datasource registry."""
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Dict, Optional

from ...core.config import Settings, get_settings
from ...models.datasource import DatasourceRecord

logger = logging.getLogger(__name__)


class DatasourceRepository:
    """Thread-safe load/save of datasource records to ``registry.json``."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        self._lock = threading.RLock()
        os.makedirs(self._settings.files_dir, exist_ok=True)
        self._records: Dict[str, DatasourceRecord] = self._load()

    @property
    def files_dir(self) -> str:
        return self._settings.files_dir

    @property
    def registry_path(self) -> str:
        return self._settings.registry_path

    def list_all(self) -> list[DatasourceRecord]:
        with self._lock:
            return list(self._records.values())

    def get(self, datasource_id: str) -> Optional[DatasourceRecord]:
        with self._lock:
            return self._records.get(datasource_id)

    def save(self, record: DatasourceRecord) -> None:
        with self._lock:
            self._records[record.id] = record
            self._persist()

    def delete(self, datasource_id: str) -> Optional[DatasourceRecord]:
        with self._lock:
            record = self._records.pop(datasource_id, None)
            if record is not None:
                self._persist()
            return record

    def update(self, datasource_id: str, **updates: object) -> None:
        with self._lock:
            record = self._records.get(datasource_id)
            if record is None:
                return
            data = record.model_dump()
            data.update(updates)
            self._records[datasource_id] = DatasourceRecord(**data)
            self._persist()

    def replace_all(self, records: Dict[str, DatasourceRecord]) -> None:
        with self._lock:
            self._records = dict(records)
            self._persist()

    def _load(self) -> Dict[str, DatasourceRecord]:
        if not os.path.exists(self._settings.registry_path):
            return {}
        try:
            with open(self._settings.registry_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as exc:
            logger.warning("Failed to load registry file, starting empty: %s", exc)
            return {}

        records: Dict[str, DatasourceRecord] = {}
        for ds_id, payload in raw.items():
            try:
                records[ds_id] = DatasourceRecord(**payload)
            except Exception as exc:
                logger.warning("Skipping invalid registry entry %s: %s", ds_id, exc)
        return records

    def _persist(self) -> None:
        serialised = {
            ds_id: json.loads(record.model_dump_json())
            for ds_id, record in self._records.items()
        }
        tmp = self._settings.registry_path + ".tmp"
        os.makedirs(os.path.dirname(self._settings.registry_path), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(serialised, f, indent=2, default=str)
        os.replace(tmp, self._settings.registry_path)
