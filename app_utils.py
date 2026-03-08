from __future__ import annotations

import os
import posixpath
from urllib.parse import urlparse
from urllib.parse import unquote

_WINDOWS_INVALID_CHARS = '<>:"/\\|?*'


def _default_port(scheme: str) -> int | None:
    if scheme == "http":
        return 80
    if scheme == "https":
        return 443
    return None


def _normalize_url_path(path: str) -> str:
    raw = unquote(path or "/")
    keep_trailing = raw.endswith("/")
    normalized = posixpath.normpath(raw)
    if normalized == ".":
        normalized = "/"
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    if keep_trailing and normalized != "/":
        normalized = f"{normalized}/"
    return normalized


def is_url_in_scope(base_url: str, candidate_url: str) -> bool:
    base = urlparse(base_url)
    candidate = urlparse(candidate_url)

    if not base.scheme or not base.netloc or not candidate.scheme or not candidate.netloc:
        return False

    base_scheme = base.scheme.lower()
    candidate_scheme = candidate.scheme.lower()
    if base_scheme != candidate_scheme:
        return False

    if (base.hostname or "").lower() != (candidate.hostname or "").lower():
        return False

    base_port = base.port or _default_port(base_scheme)
    candidate_port = candidate.port or _default_port(candidate_scheme)
    if base_port != candidate_port:
        return False

    base_path = _normalize_url_path(base.path)
    candidate_path = _normalize_url_path(candidate.path)

    if base_path == "/":
        return True

    base_prefix = base_path.rstrip("/")
    return candidate_path == base_prefix or candidate_path.startswith(f"{base_prefix}/")


def sanitize_path_segment(name: str) -> str:
    value = unquote(str(name or ""))
    value = value.replace("/", "_").replace("\\", "_")
    value = "".join("_" if ch in _WINDOWS_INVALID_CHARS else ch for ch in value)
    value = value.strip().rstrip(" .")
    if not value or value in {".", ".."}:
        return "_"
    return value


def sanitize_filename(name: str) -> str:
    return sanitize_path_segment(name)


def safe_join(root: str, parts: list[str]) -> str:
    root_real = os.path.realpath(root)
    target = os.path.realpath(os.path.join(root_real, *parts))
    try:
        if os.path.commonpath([root_real, target]) != root_real:
            raise ValueError("Path escapes root")
    except ValueError as ex:
        raise ValueError("Path escapes root") from ex
    return target


def normalize_extension(file_name: str) -> str:
    ext = os.path.splitext(file_name)[1].lower()
    if not ext:
        ext = "(No Extension)"
    if ext.startswith("."):
        ext = ext[1:]
    return f".{ext}"


def shorten_path(path: str, keep: int = 30) -> str:
    if len(path) <= keep:
        return path
    return f"...{path[-keep:]}"


def default_download_folder(url: str, fallback_root: str) -> str:
    parsed_url = urlparse(url)
    site_name = parsed_url.netloc.replace(":", "_")
    if not site_name:
        site_name = "downloads"
    return os.path.join(fallback_root, site_name)
