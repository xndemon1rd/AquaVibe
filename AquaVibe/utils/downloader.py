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
from yt_dlp.utils import match_filter_func

from AquaVibe.core.dir import CACHE_DIR, DOWNLOAD_DIR
from config import DIRECT_DOWNLOAD_TIMEOUT, MAX_DOWNLOAD_BYTES
from AquaVibe.log_config import LOGGER as _LOGGER
from AquaVibe.utils.cookie_handler import COOKIE_PATH

LOGGER = _LOGGER(__name__)


def _is_youtube_url(link: str) -> bool:
    try:
        host = (urlparse(link).hostname or "").lower()
        return host == "youtube.com" or host.endswith(".youtube.com") or host == "youtu.be" or host.endswith(".youtu.be")
    except Exception:
        return False


def _youtube_ytdlp_opts() -> dict:
    """yt-dlp options for YouTube.

    * ``js_runtimes``: yt-dlp only enables Deno by default. The image ships
      Node (>=22), so it must be enabled explicitly or YouTube signature/n
      challenges cannot be solved and formats come back empty.
    * player_client is intentionally NOT forced: yt-dlp maintains its own
      up-to-date client list; pinning old clients breaks when YouTube changes.
    * The bgutil PO-token provider is picked up automatically via the plugin.
    """
    opts = {
        "js_runtimes": {"node": {}},
        "extractor_args": {
            "youtubepot-bgutilhttp": {"base_url": ["http://127.0.0.1:4416"]},
        },
    }
    try:
        path = str(COOKIE_PATH)
        if path and os.path.isfile(path) and os.path.getsize(path) > 0:
            opts["cookiefile"] = path
    except Exception:
        pass
    return opts


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


_MEDIA_EXTS = (
    ".mp3", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wav", ".flac", ".weba",
    ".mp4", ".m4v", ".mkv", ".webm", ".mov", ".ts", ".m3u8", ".mpd", ".pls", ".m3u",
)
_NON_MEDIA_TYPES = ("text/html", "application/xhtml", "application/json", "text/plain", "text/xml", "application/xml")
_MEDIA_TYPES = ("audio/", "video/", "application/vnd.apple.mpegurl", "application/x-mpegurl",
                "application/dash+xml", "application/ogg", "application/octet-stream", "binary/octet-stream")


async def probe_media_url(url: str) -> tuple:
    """Check that a user-supplied URL points at real media, not a web page.

    Returns ``(ok, reason)``. ``ok`` is False only when we are confident the URL
    is unplayable (private host, HTTP error, or an HTML/JSON page); on network
    hiccups we fail open and let FFmpeg decide.
    """
    if not await _validate_public_url(url):
        return False, "The link is not a public http(s) address."
    path = urlparse(url).path.lower()
    try:
        session = await get_http_session()
        headers = {"Range": "bytes=0-1023", "User-Agent": "Mozilla/5.0 (compatible; AquaVibe/1.0)"}
        async with session.get(url, headers=headers, allow_redirects=True,
                               timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status >= 400:
                return False, f"The server answered HTTP {resp.status}."
            ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if any(ctype.startswith(t) for t in _NON_MEDIA_TYPES):
                return False, ("This link is a web page, not a direct audio/video file. "
                               "Send a direct media URL (.mp3/.mp4/.m3u8), or search by name.")
            if ctype and not (any(ctype.startswith(t) for t in _MEDIA_TYPES) or path.endswith(_MEDIA_EXTS)):
                return False, f"Unsupported content type: {ctype}."
            head = await resp.content.read(512)
            if head.lstrip()[:15].lower().startswith((b"<!doctype html", b"<html")):
                return False, "This link is a web page, not a direct audio/video file."
    except Exception as exc:
        LOGGER.warning("probe_media_url could not check %r (%r); letting FFmpeg try", url, exc)
    return True, ""


def _classify_ytdlp_error(msg: str) -> str:
    low = (msg or "").lower()
    if "sign in to confirm" in low or "not a bot" in low:
        return "YOUTUBE_BOT_CHECK: datacenter IP blocked - set fresh COOKIE_URL/COOKIE_DATA_B64 cookies. | " + msg
    if "po token" in low or "po_token" in low:
        return "PO_TOKEN: bgutil server on 127.0.0.1:4416 not answering. | " + msg
    if "requested format is not available" in low:
        return "FORMAT_UNAVAILABLE: retry with looser format / update yt-dlp. | " + msg
    if "video unavailable" in low or "private video" in low or "removed" in low:
        return "VIDEO_UNAVAILABLE: | " + msg
    if "unsupported url" in low:
        return "UNSUPPORTED_URL: | " + msg
    return msg


def _final_path(info: dict, requested: Optional[str] = None) -> Optional[str]:
    candidates = []
    # yt-dlp records the real post-processed file here; prefer it over guessing.
    try:
        for item in (info or {}).get("requested_downloads") or []:
            if item.get("filepath"):
                candidates.append(item["filepath"])
    except Exception:
        pass
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




LAST_ERROR: Dict[str, str] = {}


def _safe_name(title: str, fallback: str) -> str:
    cleaned = "".join(c for c in (title or "") if c.isascii() and (c.isalnum() or c in " ._-")).strip()[:60]
    return cleaned or fallback


def _download_sync(link: str, media_type: str, title: str = "", file_id: str = "") -> Optional[str]:
    if not link:
        return None
    # Name files by a unique id (video id / URL hash) so two different tracks
    # can never collide on the same file (non-ASCII titles all became "track").
    import hashlib

    uid = file_id or hashlib.sha1(f"{media_type}:{link}".encode()).hexdigest()[:12]
    base = f"{_safe_name(title, 'track')}_{uid}" if title else uid
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "outtmpl": str(Path(DOWNLOAD_DIR) / f"{base}.%(ext)s"),
        "noprogress": True,
        "continuedl": True,
        "overwrites": False,
        "retries": 2,
        "fragment_retries": 2,
        "socket_timeout": 20,
        "cachedir": str(CACHE_DIR),
        "max_filesize": MAX_DOWNLOAD_BYTES,
        # Speed: skip per-format HEAD probing and pull DASH/HLS fragments in
        # parallel. (.part files are kept on purpose so an interrupted download
        # is never mistaken for a finished one.)
        "check_formats": False,
        "concurrent_fragment_downloads": 4,
        "format": "bestvideo[height<=720]+bestaudio/best[height<=720]/best" if media_type == "video" else "bestaudio/best",
    }
    if _is_youtube_url(link):
        opts.update(_youtube_ytdlp_opts())
    else:
        try:
            if COOKIE_PATH.exists() and COOKIE_PATH.stat().st_size > 0:
                opts["cookiefile"] = str(COOKIE_PATH)
        except Exception:
            pass
    if media_type == "video":
        opts["merge_output_format"] = "mp4"
        # Live streams can never finish downloading; skip them so the caller
        # falls back to the direct stream URL (see YouTubeAPI.download).
        opts["match_filter"] = match_filter_func("!is_live")
    # Try the preferred format first, then progressively looser ones, so one
    # "Requested format is not available" does not kill the whole /play.
    if media_type == "video":
        format_chain = [opts["format"], "best[height<=720]/best", "best"]
    else:
        format_chain = ["bestaudio/best", "best"]
    last_exc: Optional[Exception] = None
    for fmt in format_chain:
        attempt = dict(opts, format=fmt)
        try:
            with YoutubeDL(attempt) as ydl:
                info = ydl.extract_info(link, download=True)
                if not info:
                    LAST_ERROR[link] = "yt-dlp returned no info"
                    continue
                if isinstance(info, dict) and info.get("is_live"):
                    # Skipped by match_filter; no other format will change that.
                    LAST_ERROR[link] = "live stream - use direct stream URL"
                    return None
                path = _final_path(info, ydl.prepare_filename(info))
                if path:
                    LAST_ERROR.pop(link, None)
                    return path
                LAST_ERROR[link] = "download finished but output file not found (max_filesize/format skip?)"
                LOGGER.error("yt-dlp finished for %r but no output file was found (base=%s, format=%s)", link, base, fmt)
        except Exception as exc:
            last_exc = exc
            LAST_ERROR[link] = _classify_ytdlp_error(str(exc))[:400]
            # ERROR level so the real reason is visible in Railway logs.
            LOGGER.error("yt-dlp failed for %r (format=%s): %s", link, fmt, exc)
            low = str(exc).lower()
            # Bot-check / private / unavailable will not be fixed by another format.
            if "requested format is not available" not in low:
                break
    return None


async def media_download(link: str, type: str, title: str = "", file_id: str = "") -> Optional[str]:
    """Download a public media URL for supported providers."""
    key = f"{type}:{link}"
    async with _inflight_lock:
        existing = _inflight.get(key)
        if existing:
            return await existing
        fut = asyncio.get_running_loop().create_future()
        _inflight[key] = fut
    try:
        result = await asyncio.to_thread(_download_sync, link, type, title, file_id)
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
