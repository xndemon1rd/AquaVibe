"""Lightweight disk protection for long-running Railway/Termux deployments."""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from config import (
    CACHE_RETENTION_HOURS,
    DOWNLOAD_RETENTION_HOURS,
    MAX_CACHE_BYTES,
    MAX_DOWNLOAD_BYTES,
    STORAGE_CLEANUP_INTERVAL,
)
from AquaVibe.log_config import LOGGER

LOGGER = LOGGER(__name__)
ROOT = Path.cwd()
MANAGED_DIRS = (ROOT / "downloads", ROOT / "cache", ROOT / "playback")


def _files(directory: Path):
    if not directory.exists():
        return []
    result = []
    for path in directory.rglob("*"):
        try:
            if path.is_file():
                result.append((path, path.stat().st_size, path.stat().st_mtime))
        except OSError:
            continue
    return result


def _delete(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def cleanup_storage_once() -> dict:
    now = time.time()
    removed = 0
    removed_bytes = 0

    # Old temporary media is the main source of disk exhaustion. Keep recent
    # files untouched so an active stream/upload is not removed underneath it.
    for directory, hours in (
        (ROOT / "downloads", DOWNLOAD_RETENTION_HOURS),
        (ROOT / "playback", DOWNLOAD_RETENTION_HOURS),
        (ROOT / "cache", CACHE_RETENTION_HOURS),
    ):
        cutoff = now - max(1, hours) * 3600
        for path, size, mtime in _files(directory):
            if mtime >= cutoff:
                continue
            _delete(path)
            if not path.exists():
                removed += 1
                removed_bytes += size

    # Enforce a hard-ish cache budget as well. Files are removed oldest-first,
    # but anything modified in the last hour is protected.
    cache_files = sorted(_files(ROOT / "cache"), key=lambda item: item[2])
    cache_total = sum(item[1] for item in cache_files)
    target = int(MAX_CACHE_BYTES * 0.85)
    if cache_total > MAX_CACHE_BYTES:
        protected_cutoff = now - 3600
        for path, size, mtime in cache_files:
            if cache_total <= target:
                break
            if mtime >= protected_cutoff:
                continue
            _delete(path)
            if not path.exists():
                cache_total -= size
                removed += 1
                removed_bytes += size

    # Keep the process logs bounded too. They are diagnostic, not application
    # state and should never be allowed to consume the whole container disk.
    for name in ("runtime.log", "ignored_errors.log", "self_healing_errors.jsonl"):
        path = ROOT / name
        try:
            if path.exists() and path.stat().st_size > 10 * 1024 * 1024:
                with path.open("rb") as fh:
                    fh.seek(-5 * 1024 * 1024, os.SEEK_END)
                    tail = fh.read()
                old_size = path.stat().st_size
                tmp = path.with_suffix(path.suffix + ".tmp")
                tmp.write_bytes(tail)
                tmp.replace(path)
                removed += 1
                removed_bytes += max(0, old_size - len(tail))
        except OSError:
            continue

    return {"removed_files": removed, "freed_bytes": removed_bytes}


async def storage_maintenance_loop() -> None:
    while True:
        try:
            result = await asyncio.to_thread(cleanup_storage_once)
            if result["removed_files"]:
                LOGGER.info(
                    "Storage guard removed %s old files (~%s bytes)",
                    result["removed_files"], result["freed_bytes"],
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            LOGGER.warning("Storage guard failed: %s", exc)
        await asyncio.sleep(max(300, STORAGE_CLEANUP_INTERVAL))
