"""URL safety checks for outbound web data fetch."""
from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urlparse

# Government, open-data, and common trusted research hosts (suffix match).
DEFAULT_TRUSTED_DOMAIN_SUFFIXES: tuple[str, ...] = (
    ".gov",
    ".gov.uk",
    ".gov.au",
    ".edu",
    ".ac.uk",
    "data.gov",
    "census.gov",
    "worldbank.org",
    "data.worldbank.org",
    "ourworldindata.org",
    "oecd.org",
    "data.oecd.org",
    "europa.eu",
    "ec.europa.eu",
    "who.int",
    "un.org",
    "data.un.org",
    "github.com",
    "raw.githubusercontent.com",
    "archive.ics.uci.edu",
    "kaggle.com",
    "datahub.io",
    "openstreetmap.org",
    "wikimedia.org",
    "statista.com",
    "fred.stlouisfed.org",
    "data.cms.gov",
    "data.nasa.gov",
    "data.gov.uk",
    "data.gov.au",
    "data.europa.eu",
)

DATA_FILE_EXTENSIONS: tuple[str, ...] = (
    ".csv",
    ".tsv",
    ".json",
    ".jsonl",
    ".parquet",
    ".xlsx",
    ".xls",
    ".zip",
)

_BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "metadata.google.internal",
    "metadata.google",
}


@dataclass(frozen=True)
class UrlValidationResult:
    ok: bool
    reason: str = ""
    trust_score: int = 0
    is_data_file: bool = False


def _hostname_from_url(url: str) -> str:
    parsed = urlparse(url)
    return (parsed.hostname or "").lower().strip(".")


def _is_private_ip(hostname: str) -> bool:
    try:
        addr = ipaddress.ip_address(hostname)
        return bool(
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
        )
    except ValueError:
        return False


def _resolve_host_ips(hostname: str) -> List[str]:
    try:
        infos = socket.getaddrinfo(hostname, None)
        return list({item[4][0] for item in infos})
    except OSError:
        return []


def domain_trust_score(hostname: str, extra_suffixes: Optional[List[str]] = None) -> int:
    if not hostname:
        return 0
    host = hostname.lower()
    suffixes = list(DEFAULT_TRUSTED_DOMAIN_SUFFIXES)
    if extra_suffixes:
        suffixes.extend(s.lower() for s in extra_suffixes)

    score = 0
    for suffix in suffixes:
        if host == suffix.lstrip(".") or host.endswith(suffix):
            score = max(score, 80 if suffix.startswith(".gov") else 60)
    if host.endswith(".org") or host.endswith(".int"):
        score = max(score, 40)
    return score


def looks_like_data_file(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in DATA_FILE_EXTENSIONS)


def validate_fetch_url(
    url: str,
    *,
    allow_untrusted: bool = False,
    extra_trusted_suffixes: Optional[List[str]] = None,
) -> UrlValidationResult:
    if not url or not url.strip():
        return UrlValidationResult(ok=False, reason="URL is empty")

    parsed = urlparse(url.strip())
    if parsed.scheme not in {"https"}:
        return UrlValidationResult(ok=False, reason="Only HTTPS URLs are allowed")

    hostname = _hostname_from_url(url)
    if not hostname:
        return UrlValidationResult(ok=False, reason="URL has no hostname")

    if hostname in _BLOCKED_HOSTS or hostname.endswith(".local"):
        return UrlValidationResult(ok=False, reason=f"Blocked host: {hostname}")

    if _is_private_ip(hostname):
        return UrlValidationResult(ok=False, reason="Private/reserved IP addresses are blocked")

    for ip in _resolve_host_ips(hostname):
        if _is_private_ip(ip):
            return UrlValidationResult(ok=False, reason=f"Host resolves to private IP: {ip}")

    trust = domain_trust_score(hostname, extra_trusted_suffixes)
    is_data = looks_like_data_file(url)

    if allow_untrusted:
        return UrlValidationResult(ok=True, trust_score=trust, is_data_file=is_data)

    if trust >= 40 or (is_data and trust >= 20):
        return UrlValidationResult(ok=True, trust_score=trust, is_data_file=is_data)

    if is_data and re.search(r"(download|dataset|data|api|export)", url, re.I):
        return UrlValidationResult(ok=True, trust_score=trust + 10, is_data_file=True)

    return UrlValidationResult(
        ok=False,
        reason=(
            f"Untrusted domain '{hostname}'. "
            "Only known open-data / government / research hosts or direct data file URLs are allowed."
        ),
        trust_score=trust,
        is_data_file=is_data,
    )
