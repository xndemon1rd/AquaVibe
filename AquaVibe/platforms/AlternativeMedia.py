"""Supported alternative media providers for AquaVibe.

Supported providers:
- PeerTube
- Dailymotion
- Vimeo
- Rumble
- Odysee
"""
import asyncio
import os
import re
import urllib.parse
from typing import Any, Dict, Iterable, List, Optional, Tuple

import aiofiles
import aiohttp
from bs4 import BeautifulSoup
from yt_dlp import YoutubeDL

from AquaVibe.utils.formatters import seconds_to_min
from config import MAX_DOWNLOAD_BYTES

_PROVIDER_RE = {
    "Dailymotion": re.compile(r"(?:^|//)(?:www\.)?dailymotion\.[a-z]{2,3}/", re.I),
    "Vimeo": re.compile(r"(?:^|//)(?:www\.)?vimeo\.com/", re.I),
    "Rumble": re.compile(r"(?:^|//)(?:www\.)?rumble\.com/", re.I),
    "Odysee": re.compile(r"(?:^|//)(?:www\.)?odysee\.com/", re.I),
    "PeerTube": re.compile(r"https?://[^/]+/(?:w/|videos/watch/|videos/embed/|video-channels/)", re.I),
    "SoundCloud": re.compile(r"(?:^|//)(?:www\.)?soundcloud\.com/", re.I),
}
_DIRECT_MEDIA_RE = re.compile(r"\.(?:mp3|m4a|aac|ogg|oga|opus|wav|flac|webm|mp4|mkv|mov)(?:\?.*)?$", re.I)
_HLS_RE = re.compile(r"(?:\.m3u8(?:\?.*)?|/hls(?:/|$)|/manifest(?:/|$))", re.I)
_PEERTUBE_SEARCH = "https://peertube.cpy.re/api/v1/search/videos"
_ODYSEE_SEARCH = "https://lighthouse.odysee.tv/search"
_ODYSEE_PLAYER = "https://player.odycdn.com/api/v3/streams/free"


class AlternativeMediaAPI:
    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=25, connect=10, sock_read=20)
        self._cache: Dict[str, Tuple[float, Dict[str, Any], str]] = {}
        self._cache_ttl = 180

    @staticmethod
    def _provider(url: str) -> Optional[str]:
        value = str(url or "").strip()
        for name, pattern in _PROVIDER_RE.items():
            if pattern.search(value):
                return name
        return None

    @classmethod
    def valid(cls, url: str) -> bool:
        value = str(url or "").strip()
        return cls._provider(value) is not None or cls.is_direct_media(value)

    @staticmethod
    def is_direct_media(url: str) -> bool:
        value = str(url or "").strip()
        return bool(_DIRECT_MEDIA_RE.search(value) or _HLS_RE.search(value))

    @staticmethod
    def is_hls(url: str) -> bool:
        return bool(_HLS_RE.search(str(url or "")))

    @staticmethod
    def _duration(value: Any) -> int:
        try:
            return max(0, int(float(value or 0)))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _score(title: str, query: str, uploader: str = "") -> float:
        title_cf = re.sub(r"[^a-z0-9\s]", " ", str(title or "").casefold())
        q = re.sub(r"[^a-z0-9\s]", " ", str(query or "").casefold()).strip()
        tokens = [x for x in q.split() if x]
        score = 0.0
        if q and q in title_cf:
            score += 60
        matched = 0
        uploader_cf = str(uploader or "").casefold()
        for token in tokens:
            if token in title_cf:
                score += 7
                matched += 1
            if token in uploader_cf:
                score += 2
        if tokens:
            score += 20 * (matched / len(tokens))
        return score

    @classmethod
    def _normalise(cls, info: Dict[str, Any], provider: Optional[str] = None) -> Dict[str, Any]:
        link = str(info.get("webpage_url") or info.get("original_url") or info.get("url") or "").strip()
        provider = provider or cls._provider(link) or "Direct Media"
        if not link:
            raise LookupError("Unsupported or blocked media URL")
        title = str(info.get("title") or "Alternative Media Track").strip()
        uploader = str(info.get("artist") or info.get("uploader") or info.get("channel") or provider).strip()
        duration = cls._duration(info.get("duration"))
        return {
            "title": title,
            "artist": uploader,
            "duration_min": seconds_to_min(duration),
            "duration_sec": duration,
            "thumb": str(info.get("thumbnail") or ""),
            "link": link,
            "vidid": f"alt:{provider.lower()}:{info.get('id') or abs(hash(link))}",
            "track_id": str(info.get("id") or link),
            "streamable": True,
            "media_type": "video",
            "audio_url": link,
            "source": provider,
            "license": "",
        }

    @staticmethod
    async def _json(url: str, params: Dict[str, Any]) -> Any:
        async with aiohttp.ClientSession(timeout=AlternativeMediaAPI().timeout, headers={"User-Agent": "AquaVibe/1.0"}) as session:
            async with session.get(url, params=params, allow_redirects=True) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}")
                return await response.json(content_type=None)

    @staticmethod
    def _odysee_parts(url: str) -> Optional[Tuple[str, str]]:
        """Extract Odysee claim name/id from a public Odysee URL."""
        try:
            path = urllib.parse.urlparse(str(url)).path.strip("/")
            if not path:
                return None
            tail = urllib.parse.unquote(path.split("/")[-1])
            if ":" not in tail:
                return None
            name, claim_id = tail.rsplit(":", 1)
            name = name.strip()
            claim_id = claim_id.strip()
            if not name or not re.fullmatch(r"[0-9a-fA-F]{40}", claim_id):
                return None
            return name, claim_id
        except Exception:
            return None

    @classmethod
    def _odysee_claim_uri(cls, url: str) -> Optional[str]:
        parts = cls._odysee_parts(url)
        if not parts:
            return None
        name, claim_id = parts
        return f"lbry://{name}#{claim_id}"

    @classmethod
    def _extract_streaming_url(cls, payload: Any) -> Optional[str]:
        if isinstance(payload, dict):
            for key in ("streaming_url", "streamingUrl"):
                value = payload.get(key)
                if isinstance(value, str) and value.startswith(("http://", "https://")):
                    return value
            for key in ("result", "response", "data", "value", "outputs"):
                found = cls._extract_streaming_url(payload.get(key))
                if found:
                    return found
        elif isinstance(payload, list):
            for item in payload:
                found = cls._extract_streaming_url(item)
                if found:
                    return found
        return None

    @classmethod
    def _extract_sd_hash(cls, payload: Any) -> Optional[str]:
        if isinstance(payload, dict):
            for key in ("sd_hash", "sdHash"):
                value = payload.get(key)
                if isinstance(value, str) and value:
                    return value
            for key in ("result", "response", "data", "value", "source", "outputs"):
                found = cls._extract_sd_hash(payload.get(key))
                if found:
                    return found
        elif isinstance(payload, list):
            for item in payload:
                found = cls._extract_sd_hash(item)
                if found:
                    return found
        return None

    async def _odysee_info(self, url: str) -> Optional[Dict[str, Any]]:
        parts = self._odysee_parts(url)
        claim_uri = self._odysee_claim_uri(url)
        if not parts or not claim_uri:
            return None
        name, claim_id = parts
        headers = {"User-Agent": "AquaVibe/1.0", "Accept": "application/json"}
        stream_url = None

        # Resolve through Odysee's current SDK proxy. This is the same service
        # family used by Odysee's official clients and returns the actual CDN
        # streaming_url when one is available.
        get_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "get",
            "params": {"uri": claim_uri, "save_file": False},
        }
        try:
            async with aiohttp.ClientSession(timeout=self.timeout, headers=headers) as session:
                async with session.post(
                    "https://api.na-backend.odysee.com/api/v1/proxy?m=get",
                    json=get_payload,
                    allow_redirects=True,
                ) as response:
                    if response.status == 200:
                        data = await response.json(content_type=None)
                        stream_url = self._extract_streaming_url(data)
        except Exception:
            stream_url = None

        # Fallback to resolve metadata. Current Odysee clients prefer the
        # SDK-provided streaming_url; when it is unavailable, try the public
        # player CDN variants used by the current frontend. Do not require an
        # sd_hash in the URL because the public free stream endpoint also
        # supports the claim path ending in video.mp4.
        if not stream_url:
            resolve_payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resolve",
                "params": {"urls": [claim_uri]},
            }
            sd_hash = None
            try:
                async with aiohttp.ClientSession(timeout=self.timeout, headers=headers) as session:
                    async with session.post(
                        "https://api.na-backend.odysee.com/api/v1/proxy?m=resolve",
                        json=resolve_payload,
                        allow_redirects=True,
                    ) as response:
                        if response.status == 200:
                            data = await response.json(content_type=None)
                            sd_hash = self._extract_sd_hash(data)
            except Exception:
                sd_hash = None

            name_q = urllib.parse.quote(name, safe="")
            claim_q = urllib.parse.quote(claim_id, safe="")
            candidates = [
                f"{_ODYSEE_PLAYER}/{name_q}/{claim_q}/video.mp4",
            ]
            if sd_hash:
                sd_q = urllib.parse.quote(str(sd_hash), safe="")
                candidates.extend([
                    f"{_ODYSEE_PLAYER}/{name_q}/{claim_q}/{sd_q}.mp4",
                    f"{_ODYSEE_PLAYER}/{name_q}/{claim_q}/{sd_q[:40]}.mp4",
                ])

            # Probe the candidate CDN URLs so a later download does not fail
            # merely because the first documented variant is unavailable.
            try:
                async with aiohttp.ClientSession(timeout=self.timeout, headers={**headers, "Referer": "https://odysee.com/"}) as session:
                    for candidate in candidates:
                        try:
                            async with session.get(candidate, allow_redirects=True) as response:
                                if response.status == 200:
                                    ctype = (response.headers.get("Content-Type") or "").lower()
                                    if "video" in ctype or "audio" in ctype or "octet-stream" in ctype:
                                        stream_url = str(response.url)
                                        break
                        except Exception:
                            continue
            except Exception:
                stream_url = None

        if not stream_url:
            return None
        return {
            "id": claim_id,
            "title": name.replace("-", " "),
            "uploader": "Odysee",
            "duration": 0,
            "webpage_url": url,
            "url": stream_url,
            "thumbnail": "",
        }

    async def _yt_info(self, url: str) -> Dict[str, Any]:
        # Never send Odysee/LBRY URLs through yt-dlp. Odysee has a public CDN
        # playback path and its yt-dlp extractor is the source of the [lbr]
        # "No video formats found" errors seen in Railway logs.
        if self._provider(url) == "Odysee":
            info = await self._odysee_info(url)
            if info:
                return info
            raise LookupError("Invalid Odysee media URL")

        def _run():
            opts = {
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "skip_download": True,
                "extract_flat": False,
            }
            with YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)
        return await asyncio.to_thread(_run)

    async def resolve_identifier(self, identifier: str) -> Optional[Tuple[Dict[str, Any], str]]:
        target = str(identifier or "")
        for _key, (_ts, details, callback_id) in self._cache.items():
            if str(details.get("vidid") or "") == target or str(callback_id or "") == target:
                return details, str(callback_id or details.get("link") or target)
        return None

    async def track(self, url: str) -> Tuple[Dict[str, Any], str]:
        provider = self._provider(url)
        if not provider and not self.is_direct_media(url):
            raise LookupError("Unsupported media provider")
        if not provider and self.is_direct_media(url):
            parsed = urllib.parse.urlparse(str(url))
            name = os.path.basename(parsed.path) or "Direct Media"
            title = urllib.parse.unquote(os.path.splitext(name)[0]) or "Direct Media"
            details = {
                "title": title.replace("_", " "),
                "artist": "Direct Media",
                "duration_min": "00:00",
                "duration_sec": 0,
                "thumb": "",
                "link": str(url),
                "vidid": f"direct:{abs(hash(url))}",
                "track_id": str(url),
                "streamable": True,
                "media_type": "video" if re.search(r"\.(?:mp4|mkv|mov|webm)(?:\?.*)?$", str(url), re.I) else "audio",
                "audio_url": str(url),
                "source": "Direct Media",
                "license": "",
            }
            return details, details["vidid"]
        info = await self._yt_info(url)
        if not isinstance(info, dict):
            raise LookupError("Media provider returned no metadata")
        details = self._normalise(info, provider)
        return details, details["vidid"]

    async def _soundcloud_candidates(self, query: str) -> List[str]:
        def _run():
            opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": True,
                "skip_download": True,
                "noplaylist": True,
            }
            with YoutubeDL(opts) as ydl:
                data = ydl.extract_info(f"scsearch8:{query}", download=False)
                return data or {}
        try:
            data = await asyncio.to_thread(_run)
            out = []
            for item in (data.get("entries") or []):
                if not isinstance(item, dict):
                    continue
                link = item.get("webpage_url") or item.get("original_url") or item.get("url")
                if link and self._provider(str(link)) == "SoundCloud":
                    out.append(str(link))
            return out
        except Exception:
            return []

    async def _dailymotion_candidates(self, query: str) -> List[str]:
        search_url = "https://www.dailymotion.com/search/{}/videos".format(urllib.parse.quote(query, safe=""))
        def _run():
            opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True, "noplaylist": False}
            with YoutubeDL(opts) as ydl:
                return ydl.extract_info(search_url, download=False)
        try:
            data = await asyncio.to_thread(_run)
            return [str(x.get("webpage_url") or x.get("url") or "") for x in (data or {}).get("entries") or [] if isinstance(x, dict)]
        except Exception:
            return []

    async def _page_candidates(self, url: str, provider: str, patterns: Iterable[str]) -> List[str]:
        try:
            async with aiohttp.ClientSession(timeout=self.timeout, headers={"User-Agent": "Mozilla/5.0 (compatible; AquaVibe/1.0)"}) as session:
                async with session.get(url, allow_redirects=True) as response:
                    if response.status != 200:
                        return []
                    html = await response.text(errors="ignore")
            soup = BeautifulSoup(html, "html.parser")
            out: List[str] = []
            for a in soup.find_all("a", href=True):
                href = urllib.parse.urljoin(url, a.get("href"))
                if any(re.search(p, href, re.I) for p in patterns):
                    if self._provider(href) == provider and href not in out:
                        out.append(href)
                if len(out) >= 8:
                    break
            return out
        except Exception:
            return []

    async def _peertube_candidates(self, query: str) -> List[str]:
        try:
            payload = await self._json(_PEERTUBE_SEARCH, {
                "search": query,
                "count": 8,
                "searchTarget": "search-index",
                "nsfw": "false",
                "sort": "-match",
            })
            out = []
            for item in payload.get("data") or []:
                link = item.get("url") or item.get("watchUrl") or item.get("permanentUrl")
                if link and self._provider(str(link)) == "PeerTube":
                    out.append(str(link))
            return out
        except Exception:
            return []

    async def _odysee_candidates(self, query: str) -> List[str]:
        try:
            payload = await self._json(_ODYSEE_SEARCH, {
                "s": query,
                "size": 8,
                "from": 0,
                "claimType": "file",
                "nsfw": "false",
                "free_only": "true",
            })
            out = []
            for item in payload if isinstance(payload, list) else []:
                name = item.get("name")
                claim_id = item.get("claimId") or item.get("claim_id")
                canonical = item.get("canonical_url") or item.get("canonicalUrl") or item.get("url")
                if canonical:
                    out.append(str(canonical))
                elif name and claim_id:
                    out.append(f"https://odysee.com/{urllib.parse.quote(str(name), safe='')}:{claim_id}")
            return out
        except Exception:
            return []

    async def search(self, query: str, video: bool = False) -> Tuple[Dict[str, Any], str]:
        query = str(query or "").strip()
        if not query:
            raise ValueError("Empty media query")
        key = ("video:" if video else "audio:") + query.casefold()
        now = asyncio.get_running_loop().time()
        cached = self._cache.get(key)
        if cached and now - cached[0] < self._cache_ttl:
            return cached[1], cached[2]

        dm_url = "https://www.dailymotion.com/search/{}/videos".format(urllib.parse.quote(query, safe=""))
        vimeo_url = "https://vimeo.com/search?q={}".format(urllib.parse.quote(query))
        rumble_url = "https://rumble.com/search/video?q={}".format(urllib.parse.quote(query))
        results = await asyncio.gather(
            self._soundcloud_candidates(query),
            self._dailymotion_candidates(query),
            self._peertube_candidates(query),
            self._odysee_candidates(query),
            self._page_candidates(vimeo_url, "Vimeo", [r"vimeo\.com/(?:\d+|[^/?#]+/\d+)"]),
            self._page_candidates(rumble_url, "Rumble", [r"rumble\.com/v[0-9a-z]+"]),
            return_exceptions=True,
        )
        candidates: List[str] = []
        for group in results:
            if isinstance(group, list):
                for url in group:
                    if url and url not in candidates:
                        candidates.append(url)

        scored: List[Tuple[float, Dict[str, Any], str]] = []
        for url in candidates[:24]:
            try:
                details, vidid = await self.track(url)
                score = self._score(details.get("title"), query, details.get("artist"))
                if score > 0:
                    scored.append((score, details, vidid))
            except Exception:
                continue

        if not scored:
            raise LookupError(f"No playable alternative-media result found for {query}")
        scored.sort(key=lambda x: x[0], reverse=True)
        _, details, vidid = scored[0]
        # Callback buttons must carry a resolvable source URL. The internal
        # alt:<provider>:<id> identifier is only a queue/cache identifier and
        # cannot be resolved by the alternative-provider tracker after a callback.
        callback_id = str(details.get("link") or vidid)
        self._cache[key] = (now, details, callback_id)
        return details, callback_id

    async def download(self, link: str, title: str = "", video: bool = False) -> Tuple[str, bool]:
        provider = self._provider(link)
        if not provider and self.is_direct_media(link) and not self.is_hls(link):
            from AquaVibe.utils.downloader import download_file
            from AquaVibe.core.dir import DOWNLOAD_DIR
            safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", title or "direct_media")[:70] or "direct_media"
            ext = os.path.splitext(urllib.parse.urlparse(link).path)[1].lower() or (".mp4" if video else ".mp3")
            out = os.path.join(str(DOWNLOAD_DIR), safe + ext)
            path = await download_file(link, out)
            if not path:
                raise RuntimeError("Direct media download failed")
            return path, True
        if not provider:
            raise RuntimeError("Unsupported media provider")

        # Odysee/LBRY uses its resolved public CDN media URL directly.
        if provider == "Odysee":
            info = await self._odysee_info(link)
            if not info:
                raise RuntimeError("Odysee claim could not be resolved to a playable stream")
            direct_url = str(info.get("url") or "")
            if not direct_url:
                raise RuntimeError("Odysee returned no playable stream URL")
            from AquaVibe.utils.downloader import download_file
            from AquaVibe.core.dir import DOWNLOAD_DIR
            import hashlib
            safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", title or "odysee")[:70] or "odysee"
            key = hashlib.sha256(direct_url.encode()).hexdigest()[:16]
            out = str(__import__("pathlib").Path(DOWNLOAD_DIR) / f"{safe}_{key}.mp4")
            if __import__("os").path.isfile(out) and __import__("os").path.getsize(out) > 16000:
                return out, True
            path = await download_file(direct_url, out)
            if path:
                return path, True

            # Some Odysee CDN responses require a normal browser referer and
            # user-agent. Retry the resolved URL directly before declaring the
            # provider unavailable.
            try:
                timeout = aiohttp.ClientTimeout(total=120, connect=15, sock_read=60)
                headers = {
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/128 Safari/537.36",
                    "Referer": "https://odysee.com/",
                    "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
                }
                async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                    async with session.get(direct_url, allow_redirects=True) as response:
                        if response.status == 200:
                            total = 0
                            from pathlib import Path
                            Path(out).parent.mkdir(parents=True, exist_ok=True)
                            async with aiofiles.open(out, "wb") as fp:
                                async for chunk in response.content.iter_chunked(1024 * 1024):
                                    total += len(chunk)
                                    if total > MAX_DOWNLOAD_BYTES:
                                        raise RuntimeError("Odysee media exceeds configured size limit")
                                    await fp.write(chunk)
                            if os.path.isfile(out) and os.path.getsize(out) > 16000:
                                return out, True
            except Exception:
                pass
            raise RuntimeError("Odysee direct CDN download failed")

        from AquaVibe.utils.downloader import media_download, download_file
        path = await media_download(link, type="video" if video else "audio", title=title or provider)
        if path and os.path.isfile(path) and os.path.getsize(path) > 16000:
            return str(path), True

        # Provider fallback: yt-dlp can often resolve a direct playable format
        # even when its full download pipeline fails (temporary CDN, merge, or
        # provider-specific post-processing issue). Prefer a combined format for
        # video and an audio-only format for audio.
        try:
            info = await self._yt_info(link)
            formats = info.get("formats") or []
            selected = None
            if video:
                combined = [
                    f for f in formats
                    if f.get("url") and f.get("vcodec") not in (None, "none")
                    and f.get("acodec") not in (None, "none")
                ]
                if combined:
                    selected = max(combined, key=lambda f: ((f.get("height") or 0), (f.get("tbr") or 0)))
            else:
                audio = [
                    f for f in formats
                    if f.get("url") and f.get("acodec") not in (None, "none")
                ]
                if audio:
                    selected = max(audio, key=lambda f: (f.get("abr") or 0, f.get("tbr") or 0))
            direct_url = str((selected or {}).get("url") or "")
            if direct_url and not self.is_hls(direct_url):
                from AquaVibe.core.dir import DOWNLOAD_DIR
                safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", title or provider)[:70] or "media"
                ext = ".mp4" if video else ".m4a"
                out = os.path.join(str(DOWNLOAD_DIR), safe + "_direct" + ext)
                direct_path = await download_file(direct_url, out)
                if direct_path and os.path.isfile(direct_path) and os.path.getsize(direct_path) > 16000:
                    return str(direct_path), True
        except Exception:
            pass

        raise RuntimeError(f"{provider} download failed")
