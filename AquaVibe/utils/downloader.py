"""Generic public-media downloader for supported providers.

The extractor is used only for supported public media URLs; no account cookies
or provider-specific authentication are configured here.
"""
import asyncio
import glob
import ipaddress
import os
import re
import socket
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

import aiofiles
import aiohttp
from aiohttp import TCPConnector
from yt_dlp import YoutubeDL

from AquaVibe.core.dir import CACHE_DIR, DOWNLOAD_DIR
from config import DIRECT_DOWNLOAD_TIMEOUT, MAX_DOWNLOAD_BYTES
from AquaVibe.log_config import LOGGER as _LOGGER

LOGGER = _LOGGER(__name__)
_inflight: Dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()
_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()


def _host_is_public(host: str) -> bool:
    if not host or host.lower() in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        return False
    try:
        addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    for item in addresses:
        try:
            ip = ipaddress.ip_address(item[4][0])
        except ValueError:
            return False
        if not ip.is_global:
            return False
    return True


def _validate_public_url_sync(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.hostname) and _host_is_public(parsed.hostname)
    except Exception:
        return False


async def _validate_public_url(url: str) -> bool:
    return await asyncio.to_thread(_validate_public_url_sync, url)


async def get_http_session() -> aiohttp.ClientSession:
    global _session
    if _session and not _session.closed:
        return _session
    async with _session_lock:
        if _session and not _session.closed:
            return _session
        timeout = aiohttp.ClientTimeout(total=DIRECT_DOWNLOAD_TIMEOUT, sock_connect=20, sock_read=60)
        connector = TCPConnector(limit=0, ttl_dns_cache=300, enable_cleanup_closed=True)
        _session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return _session


async def close_http_session() -> None:
    global _session
    async with _session_lock:
        if _session and not _session.closed:
            await _session.close()
        _session = None


async def download_file(url: str, out_path: str, max_bytes: int = MAX_DOWNLOAD_BYTES) -> Optional[str]:
    if not url or not await _validate_public_url(url):
        return None
    try:
        session = await get_http_session()
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            total = 0
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(out_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(1024 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        return None
                    await f.write(chunk)
        return out_path if os.path.isfile(out_path) and os.path.getsize(out_path) > 0 else None
    except Exception:
        try:
            os.remove(out_path)
        except OSError:
            pass
        return None


def _final_path(info: dict, requested: Optional[str] = None) -> Optional[str]:
    candidates = []
    if requested:
        candidates.append(requested)
        stem = os.path.splitext(requested)[0]
        for ext in ("m4a", "mp3", "opus", "webm", "mp4", "mkv"):
            candidates.append(f"{stem}.{ext}")
    vid = info.get("id") if isinstance(info, dict) else None
    if vid:
        candidates.extend(glob.glob(f"{DOWNLOAD_DIR}/{vid}.*"))
    for path in candidates:
        if path and os.path.isfile(path) and os.path.getsize(path) > 0:
            return path
    return None




def _download_sync(link: str, media_type: str, title: str = "") -> Optional[str]:
    if not link:
        return None
    safe_title = "".join(c for c in (title or "track") if c.isalnum() or c in " ._-" ).strip()[:80] or "track"
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "outtmpl": str(Path(DOWNLOAD_DIR) / f"{safe_title}.%(ext)s"),
        "noprogress": True,
        "continuedl": True,
        "overwrites": False,
        "retries": 2,
        "fragment_retries": 2,
        "socket_timeout": 20,
        "cachedir": str(CACHE_DIR),
        "max_filesize": MAX_DOWNLOAD_BYTES,
        "format": "bestvideo+bestaudio/best" if media_type == "video" else "bestaudio/best",
    }
    if media_type == "video":
        opts["merge_output_format"] = "mp4"
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link, download=True)
            if not info:
                return None
            return _final_path(info, ydl.prepare_filename(info))
    except Exception as exc:
        LOGGER.warning("Generic media extraction failed for %r: %s", link, exc)
        return None


async def media_download(link: str, type: str, title: str = "") -> Optional[str]:
    """Download a public media URL for supported providers."""
    key = f"{type}:{link}"
    async with _inflight_lock:
        existing = _inflight.get(key)
        if existing:
            return await existing
        fut = asyncio.get_running_loop().create_future()
        _inflight[key] = fut
    try:
        result = await asyncio.to_thread(_download_sync, link, type, title)
        fut.set_result(result)
        return result
    except Exception as exc:
        if not fut.done():
            fut.set_result(None)
        LOGGER.warning("Media download failed: %s", exc)
        return None
    finally:
        async with _inflight_lock:
            _inflight.pop(key, None)
