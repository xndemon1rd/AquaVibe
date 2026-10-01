"""Supported alternative media providers for AquaVibe.

Aqua Search Engine backend:
- SayaMusicAPI-compatible multi-provider aggregation
- Legal metadata, artwork, previews, and open/free streams
- Internal direct/video resolvers used only after search selection
"""
import asyncio
import os
import re
import urllib.parse
import difflib
import secrets
from typing import Any, Dict, Iterable, List, Optional, Tuple

import aiofiles
import aiohttp
from bs4 import BeautifulSoup
from yt_dlp import YoutubeDL

from AquaVibe.utils.formatters import seconds_to_min
from AquaVibe.log_config import LOGGER
from config import MAX_DOWNLOAD_BYTES

log = LOGGER(__name__)

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
_JIOSAAVN_SEARCH = "https://saavn.dev/api/search/songs"
_PIPED_INSTANCES = (
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.syncpundit.io",
    "https://pipedapi.moomoo.me",
)
_SAAVN_CDN_RE = re.compile(r"(?:^|//)(?:aac|h|jio)[a-z0-9.-]*\.saavncdn\.com/", re.I)
_SAYA_API = os.getenv("SAYA_MUSIC_API_URL", "https://sayamusicapi.shnwazdeveloperx.workers.dev").rstrip("/")
_SAYA_SEARCH = f"{_SAYA_API}/v1/search/tracks"
_SAYA_PROVIDER_ENDPOINTS = (
    ("jiosaavn", "/v1/jiosaavn/search/songs"),
    ("deezer", "/v1/deezer/search/tracks"),
    ("apple", "/v1/apple/search/songs"),
    ("audius", "/v1/audius/search/tracks"),
    ("musicbrainz", "/v1/musicbrainz/search/recordings"),
)


class AlternativeMediaAPI:
    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=25, connect=10, sock_read=20)
        self._cache: Dict[str, Tuple[float, Dict[str, Any], str]] = {}
        self._cache_ttl = 180
        self._search_sessions: Dict[str, Tuple[float, List[Dict[str, Any]], bool, str]] = {}
        self._search_session_ttl = 600

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
        return bool(_DIRECT_MEDIA_RE.search(value) or _HLS_RE.search(value) or _SAAVN_CDN_RE.search(value))

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

    @staticmethod
    def _tokens(value: str) -> List[str]:
        value = str(value or "").casefold()
        value = re.sub(r"\b(official|audio|video|lyrics?|full|hd|4k|song|music)\b", " ", value)
        return [x for x in re.findall(r"[a-z0-9]+", value) if x]

    @classmethod
    def _engine_score(cls, details: Dict[str, Any], query: str) -> float:
        title = str(details.get("title") or "")
        artist = str(details.get("artist") or details.get("uploader") or "")
        q_tokens = cls._tokens(query)
        t_tokens = cls._tokens(title)
        a_tokens = cls._tokens(artist)
        if not q_tokens or not t_tokens:
            return 0.0
        q_norm = " ".join(q_tokens)
        t_norm = " ".join(t_tokens)
        title_ratio = difflib.SequenceMatcher(None, q_norm, t_norm).ratio()
        overlap = len(set(q_tokens) & set(t_tokens)) / max(1, len(set(q_tokens)))
        phrase = 1.0 if q_norm == t_norm else (0.8 if q_norm in t_norm else 0.0)
        artist_overlap = len(set(q_tokens) & set(a_tokens)) / max(1, len(set(q_tokens)))
        score = title_ratio * 55 + overlap * 30 + phrase * 15
        if artist_overlap:
            score += artist_overlap * 20
        duration = int(details.get("duration_sec") or 0)
        if duration:
            score += 2
        year = str(details.get("year") or details.get("release_year") or "")
        if year.isdigit() and int(year) >= 2000:
            score += min(5, (int(year) - 1999) / 6)
        return score

    @classmethod
    def _dedupe_candidates(cls, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out=[]; seen=set()
        for item in candidates:
            if not isinstance(item, dict):
                continue
            key=(re.sub(r"[^a-z0-9]", "", str(item.get("title") or "").casefold()), re.sub(r"[^a-z0-9]", "", str(item.get("artist") or "").casefold()))
            if not key[0] or key in seen:
                continue
            seen.add(key); out.append(item)
        return out

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

    async def _jiosaavn_search(self, query: str) -> List[Dict[str, Any]]:
        """Search JioSaavn for audio-first playback.

        This is metadata/stream resolution only; /play never sends the request
        to YouTube. JioSaavn results include a CDN media URL when available.
        """
        try:
            async with aiohttp.ClientSession(timeout=self.timeout, headers={"User-Agent": "AquaVibe/1.0"}) as session:
                async with session.get(
                    _JIOSAAVN_SEARCH,
                    params={"query": query, "limit": 10},
                    allow_redirects=True,
                ) as response:
                    if response.status != 200:
                        return []
                    payload = await response.json(content_type=None)
            results = ((payload or {}).get("data") or {}).get("results") or []
            out: List[Dict[str, Any]] = []
            for item in results:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("name") or item.get("title") or "").strip()
                if not title:
                    continue
                artists = ((item.get("artists") or {}).get("primary") or [])
                artist = ", ".join(
                    str(a.get("name") or "").strip() for a in artists if isinstance(a, dict) and a.get("name")
                ).strip()
                downloads = item.get("downloadUrl") or []
                urls = []
                if isinstance(downloads, list):
                    for entry in downloads:
                        if isinstance(entry, dict) and entry.get("url"):
                            urls.append((entry.get("quality") or "", str(entry["url"])))
                elif isinstance(downloads, dict) and downloads.get("url"):
                    urls.append((downloads.get("quality") or "", str(downloads["url"])))
                direct_url = ""
                if urls:
                    # Prefer the highest advertised quality while avoiding an
                    # image/non-audio URL accidentally returned by the wrapper.
                    def qscore(pair):
                        m = re.search(r"(\d+)", str(pair[0]))
                        return int(m.group(1)) if m else 0
                    direct_url = max(urls, key=qscore)[1]
                if not direct_url:
                    direct_url = str(item.get("url") or "")
                if not direct_url or not (self.is_direct_media(direct_url) or self._SAAVN_CDN_RE.search(direct_url)):
                    continue
                duration = self._duration(item.get("duration"))
                thumb = ""
                images = item.get("image") or []
                if isinstance(images, list) and images:
                    for image in reversed(images):
                        if isinstance(image, dict) and image.get("url"):
                            thumb = str(image["url"])
                            break
                elif isinstance(images, str):
                    thumb = images
                out.append({
                    "title": title,
                    "artist": artist or "JioSaavn",
                    "duration_sec": duration,
                    "duration_min": seconds_to_min(duration),
                    "thumb": thumb,
                    "link": direct_url,
                    "webpage_url": str(item.get("url") or item.get("perma_url") or ""),
                    "vidid": f"jiosaavn:{item.get('id') or item.get('songId') or abs(hash(direct_url))}",
                    "source": "JioSaavn",
                    "media_type": "audio",
                    "streamable": True,
                })
            return out
        except Exception as exc:
            log.warning("JioSaavn search failed for %r: %s", query, exc)
            return []

    async def _piped_search_candidates(self, query: str) -> List[Dict[str, Any]]:
        """Fast metadata-only video search. Stream resolution is deferred until selection."""
        for base in _PIPED_INSTANCES:
            try:
                async with aiohttp.ClientSession(timeout=self.timeout, headers={"User-Agent": "AquaVibe/1.0"}) as session:
                    async with session.get(f"{base}/search", params={"q": query, "filter": "videos"}, allow_redirects=True) as response:
                        if response.status != 200:
                            continue
                        payload = await response.json(content_type=None)
                results = payload if isinstance(payload, list) else (payload.get("items") or payload.get("data") or [])
                out=[]
                for item in results[:15]:
                    if not isinstance(item, dict): continue
                    raw=str(item.get("url") or item.get("id") or "")
                    vid=raw.split("v=",1)[1].split("&",1)[0] if "v=" in raw else raw
                    title=str(item.get("title") or "").strip()
                    if not vid or not title: continue
                    out.append({
                        "title": title,
                        "artist": str(item.get("uploaderName") or item.get("uploader") or "Piped"),
                        "duration_sec": self._duration(item.get("duration")),
                        "duration_min": seconds_to_min(self._duration(item.get("duration"))),
                        "thumb": str(item.get("thumbnail") or ""),
                        "link": f"piped://{vid}",
                        "webpage_url": f"https://www.youtube.com/watch?v={vid}",
                        "vidid": f"piped:{vid}",
                        "source": "Piped",
                        "source_id": vid,
                        "media_type": "video",
                        "streamable": True,
                    })
                if out: return out
            except Exception as exc:
                log.warning("Piped search failed %s for %r: %s", base, query, exc)
        return []

    async def _resolve_piped_candidate(self, details: Dict[str, Any]) -> Dict[str, Any]:
        vid=str(details.get("source_id") or details.get("vidid") or "").split(":",1)[-1]
        if not vid: raise LookupError("Invalid Piped video id")
        for base in _PIPED_INSTANCES:
            try:
                async with aiohttp.ClientSession(timeout=self.timeout, headers={"User-Agent":"AquaVibe/1.0"}) as session:
                    async with session.get(f"{base}/streams/{urllib.parse.quote(vid, safe='')}", allow_redirects=True) as response:
                        if response.status != 200: continue
                        info=await response.json(content_type=None)
                streams=[x for x in (info.get("videoStreams") or []) if isinstance(x,dict) and x.get("url") and not x.get("videoOnly")]
                streams.sort(key=lambda x:(x.get("height") or 0, x.get("bitrate") or 0), reverse=True)
                selected=streams[0] if streams else None
                url=str((selected or {}).get("url") or info.get("hls") or "")
                if not url: continue
                details=dict(details)
                details.update({"link":url,"audio_url":url,"duration_sec":self._duration(info.get("duration") or details.get("duration_sec")),"duration_min":seconds_to_min(self._duration(info.get("duration") or details.get("duration_sec"))),"thumb":str(info.get("thumbnailUrl") or details.get("thumb") or "")})
                return details
            except Exception:
                continue
        raise LookupError("Piped stream could not be resolved")

    async def _piped_video_search(self, query: str) -> List[Dict[str, Any]]:
        """Search and resolve a playable combined A/V stream through Piped.

        Piped is used only for /vplay. It avoids direct YouTube/yt-dlp playback
        and gives PyTgCalls a normal remote media URL.
        """
        for base in _PIPED_INSTANCES:
            try:
                async with aiohttp.ClientSession(timeout=self.timeout, headers={"User-Agent": "AquaVibe/1.0"}) as session:
                    async with session.get(
                        f"{base}/search",
                        params={"q": query, "filter": "videos"},
                        allow_redirects=True,
                    ) as response:
                        if response.status != 200:
                            continue
                        payload = await response.json(content_type=None)
                    results = payload if isinstance(payload, list) else (payload.get("items") or payload.get("data") or [])
                    candidates = []
                    for item in results[:12]:
                        if not isinstance(item, dict):
                            continue
                        video_id = str(item.get("url") or item.get("id") or "")
                        if "v=" in video_id:
                            video_id = video_id.split("v=", 1)[1].split("&", 1)[0]
                        if not video_id:
                            continue
                        title = str(item.get("title") or "").strip()
                        uploader = str(item.get("uploaderName") or item.get("uploader") or "").strip()
                        score = self._score(title, query, uploader)
                        candidates.append((score, video_id, title, uploader, item))
                    candidates.sort(key=lambda x: x[0], reverse=True)
                    for _, video_id, title, uploader, item in candidates:
                        async with session.get(f"{base}/streams/{urllib.parse.quote(video_id, safe='')}", allow_redirects=True) as response:
                            if response.status != 200:
                                continue
                            stream_info = await response.json(content_type=None)
                        video_streams = [
                            x for x in (stream_info.get("videoStreams") or [])
                            if isinstance(x, dict) and x.get("url") and not x.get("videoOnly")
                        ]
                        video_streams.sort(key=lambda x: (x.get("height") or 0, x.get("bitrate") or 0), reverse=True)
                        selected = video_streams[0] if video_streams else None
                        direct_url = str((selected or {}).get("url") or stream_info.get("hls") or "")
                        if not direct_url:
                            continue
                        duration = self._duration(stream_info.get("duration") or item.get("duration"))
                        return [{
                            "title": str(stream_info.get("title") or title or "Piped Video"),
                            "artist": str(stream_info.get("uploader") or uploader or "Piped"),
                            "duration_sec": duration,
                            "duration_min": seconds_to_min(duration),
                            "thumb": str(stream_info.get("thumbnailUrl") or item.get("thumbnail") or ""),
                            "link": direct_url,
                            "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
                            "vidid": f"piped:{video_id}",
                            "source": "Piped",
                            "media_type": "video",
                            "streamable": True,
                        }]
            except Exception as exc:
                log.warning("Piped instance failed %s for %r: %s", base, query, exc)
                continue
        return []

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

    @staticmethod
    def _saya_walk(value: Any) -> Iterable[Dict[str, Any]]:
        """Yield likely track dictionaries from SayaMusicAPI's flexible JSON."""
        if isinstance(value, dict):
            # Track-shaped objects usually contain one of these keys.
            if any(k in value for k in ("title", "name", "trackName")) and any(
                k in value for k in ("artist", "artists", "artistName", "uploader", "author")
            ):
                yield value
            for child in value.values():
                yield from AlternativeMediaAPI._saya_walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from AlternativeMediaAPI._saya_walk(child)

    @staticmethod
    def _saya_artist(item: Dict[str, Any]) -> str:
        artist = item.get("artist") or item.get("artistName") or item.get("uploader") or item.get("author")
        if isinstance(artist, dict):
            artist = artist.get("name") or artist.get("title") or artist.get("artist")
        if isinstance(artist, list):
            names=[]
            for x in artist:
                if isinstance(x, dict):
                    x=x.get("name") or x.get("artistName") or x.get("title")
                if x: names.append(str(x))
            artist=", ".join(names)
        if not artist:
            artists=item.get("artists")
            if isinstance(artists, dict):
                artists=artists.get("items") or artists.get("data") or artists.get("primary") or artists.get("artists")
            if isinstance(artists, list):
                names=[]
                for x in artists:
                    if isinstance(x, dict): x=x.get("name") or x.get("artistName") or x.get("title")
                    if x: names.append(str(x))
                artist=", ".join(names)
        return str(artist or "").strip()

    @staticmethod
    def _saya_url(item: Dict[str, Any], keys: Iterable[str]) -> str:
        for key in keys:
            value=item.get(key)
            if isinstance(value, dict):
                value=value.get("url") or value.get("href") or value.get("src")
            if isinstance(value, list):
                for x in value:
                    if isinstance(x, dict): x=x.get("url") or x.get("href") or x.get("src")
                    if isinstance(x, str) and x.startswith(("http://", "https://")):
                        return x
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
        return ""

    @classmethod
    def _normalise_saya_item(cls, item: Dict[str, Any], query: str, video: bool = False) -> Optional[Dict[str, Any]]:
        title=str(item.get("title") or item.get("name") or item.get("trackName") or "").strip()
        artist=cls._saya_artist(item)
        if not title: return None
        duration=cls._duration(item.get("duration") or item.get("duration_sec") or item.get("durationMs", 0) / 1000 if isinstance(item.get("durationMs"), (int,float)) else 0)
        thumb=cls._saya_url(item, ("artwork", "artworkUrl", "artwork_url", "cover", "coverUrl", "thumbnail", "thumbnailUrl", "image"))
        stream=cls._saya_url(item, ("streamUrl", "stream_url", "stream", "audioUrl", "audio_url", "url"))
        preview=cls._saya_url(item, ("previewUrl", "preview_url", "preview", "audioPreviewUrl", "audio_preview_url"))
        page=cls._saya_url(item, ("webpage_url", "webpageUrl", "permalink", "perma_url", "link", "href"))
        source=str(item.get("source") or item.get("provider") or item.get("platform") or "SayaMusicAPI")
        source_id=str(item.get("id") or item.get("trackId") or item.get("track_id") or item.get("key") or page or title)
        # SayaMusicAPI deliberately exposes legal previews/open streams, not protected full tracks.
        playable=stream or preview
        if not playable and video:
            playable=page
        if not playable and not page:
            return None
        link=playable or page
        media_type="video" if video or str(item.get("type") or "").lower() in {"video","music-video"} else "audio"
        return {
            "title": title,
            "artist": artist or source,
            "duration_sec": duration,
            "duration_min": seconds_to_min(duration),
            "thumb": thumb,
            "link": link,
            "webpage_url": page,
            "vidid": f"saya:{source.lower()}:{source_id}",
            "track_id": source_id,
            "source": source,
            "source_id": source_id,
            "stream_url": stream,
            "preview_url": preview,
            "audio_url": stream or preview,
            "streamable": bool(playable),
            "media_type": media_type,
            "license": str(item.get("license") or ""),
            "year": str(item.get("year") or item.get("release_year") or item.get("releaseDate", ""))[:4],
        }

    async def _saya_search(self, query: str, video: bool = False) -> List[Dict[str, Any]]:
        """Central Aqua resolver backed by SayaMusicAPI's multi-provider aggregator."""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout, headers={"User-Agent": "AquaVibe/2.0 SayaEngine"}) as session:
                async with session.get(_SAYA_SEARCH, params={"q": query}, allow_redirects=True) as response:
                    if response.status != 200:
                        return []
                    payload=await response.json(content_type=None)
            out=[]; seen=set()
            for raw in self._saya_walk(payload):
                item=self._normalise_saya_item(raw, query, video=video)
                if not item: continue
                key=(re.sub(r"[^a-z0-9]", "", item["title"].casefold()), re.sub(r"[^a-z0-9]", "", item["artist"].casefold()))
                if key in seen: continue
                seen.add(key); out.append(item)
            return out
        except Exception as exc:
            log.warning("SayaMusicAPI search failed for %r: %s", query, exc)
            return []

    async def _saya_provider_search(self, query: str) -> List[Dict[str, Any]]:
        """Secondary fan-out through SayaMusicAPI's provider adapters."""
        async def one(name: str, path: str) -> List[Dict[str, Any]]:
            try:
                async with aiohttp.ClientSession(timeout=self.timeout, headers={"User-Agent": "AquaVibe/2.0 SayaEngine"}) as session:
                    async with session.get(_SAYA_API + path, params={"q": query, "query": query}, allow_redirects=True) as response:
                        if response.status != 200: return []
                        payload=await response.json(content_type=None)
                out=[]
                for raw in self._saya_walk(payload):
                    item=self._normalise_saya_item(raw, query)
                    if item:
                        item["source"] = name.title()
                        out.append(item)
                return out[:10]
            except Exception:
                return []
        groups=await asyncio.gather(*(one(n,p) for n,p in _SAYA_PROVIDER_ENDPOINTS), return_exceptions=True)
        out=[]
        for g in groups:
            if isinstance(g,list): out.extend(g)
        return out

    async def search_many(self, query: str, video: bool = False) -> List[Dict[str, Any]]:
        """Aqua Search Engine: Saya-style multi-provider aggregation + local ranking."""
        query=str(query or "").strip()
        if not query: raise ValueError("Empty media query")
        key=("video:" if video else "audio:")+query.casefold()
        now=asyncio.get_running_loop().time()
        cached=self._cache.get(key)
        if cached and now-cached[0] < self._cache_ttl:
            # Cached first result remains compatible with the legacy search API.
            pass

        # One fast aggregated request first. It already fans out across multiple
        # catalogues, so the bot does not depend on one provider's ranking.
        candidates=await self._saya_search(query, video=video)

        # If the aggregate is unavailable or too thin, fan out through Saya's
        # provider adapters in parallel. This keeps the engine source-agnostic.
        if len(candidates) < 6 or max((self._engine_score(x, query) for x in candidates), default=0) < 72:
            candidates.extend(await self._saya_provider_search(query))

        candidates=self._dedupe_candidates(candidates)
        ranked=[]
        for d in candidates:
            d=dict(d)
            d["_score"]=self._engine_score(d,query)
            # Strong exact/near-exact title matches are retained; weak/random
            # matches are filtered so the engine never silently plays nonsense.
            if d["_score"] >= 28:
                ranked.append(d)
        ranked.sort(key=lambda x:(x.get("_score",0), bool(x.get("streamable")), int(x.get("duration_sec") or 0) > 0), reverse=True)
        for d in ranked: d.pop("_score",None)
        return ranked[:60]

    async def create_search_session(self, query: str, video: bool = False) -> Tuple[str, List[Dict[str, Any]]]:
        results=await self.search_many(query, video=video)
        if not results: raise LookupError(f"No reliable match found for {query}")
        token=secrets.token_hex(4)
        now=asyncio.get_running_loop().time()
        self._search_sessions[token]=(now, results, bool(video), query)
        # purge old sessions
        for k,(ts,*_) in list(self._search_sessions.items()):
            if now-ts > self._search_session_ttl: self._search_sessions.pop(k,None)
        return token, results

    async def get_search_session(self, token: str) -> Optional[Tuple[List[Dict[str, Any]], bool, str]]:
        item=self._search_sessions.get(str(token))
        if not item: return None
        ts, results, video, query=item
        if asyncio.get_running_loop().time()-ts > self._search_session_ttl:
            self._search_sessions.pop(str(token),None); return None
        return results, video, query

    async def resolve_search_candidate(self, token: str, index: int) -> Optional[Dict[str, Any]]:
        session=await self.get_search_session(token)
        if not session: return None
        results, video, query=session
        if index < 0 or index >= len(results): return None
        d=dict(results[index])
        if d.get("source") == "Piped" and str(d.get("link","")).startswith("piped://"):
            d=await self._resolve_piped_candidate(d)

        # /vplay requires an actual video stream. SayaMusicAPI is intentionally
        # legal-first and may return track metadata/preview URLs, so the engine
        # resolves a selected result through its video adapter only when needed.
        if video and str(d.get("media_type") or "").lower() != "video":
            q=f"{d.get('title','')} {d.get('artist','')}".strip() or query
            video_candidates=await self._piped_search_candidates(q)
            if video_candidates:
                video_candidates=self._dedupe_candidates(video_candidates)
                video_candidates.sort(key=lambda x:self._engine_score(x,q), reverse=True)
                best=video_candidates[0]
                try:
                    if str(best.get("link","")).startswith("piped://"):
                        best=await self._resolve_piped_candidate(best)
                    d=best
                except Exception:
                    pass
        return d

    async def search(self, query: str, video: bool = False) -> Tuple[Dict[str, Any], str]:
        results=await self.search_many(query, video=video)
        if not results: raise LookupError(f"No reliable match found for {query}")
        details=results[0]
        callback_id=str(details.get("link") or details.get("vidid"))
        key=("video:" if video else "audio:")+str(query).casefold()
        self._cache[key]=(asyncio.get_running_loop().time(),details,callback_id)
        return details, callback_id

    async def download_full(self, link: str, title: str = "", video: bool = False) -> Tuple[str, bool]:
        """Fallback path: fully download a provider source when direct playback fails."""
        provider = self._provider(link)
        if not provider and self.is_direct_media(link):
            from AquaVibe.utils.downloader import download_file
            from AquaVibe.core.dir import DOWNLOAD_DIR
            safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", title or "direct_media")[:70] or "direct_media"
            ext = os.path.splitext(urllib.parse.urlparse(link).path)[1].lower() or (".mp4" if video else ".mp3")
            out = os.path.join(str(DOWNLOAD_DIR), safe + ext)
            path = await download_file(link, out)
            if not path:
                raise RuntimeError("Direct media download failed")
            return path, False
        if not provider:
            raise RuntimeError("Unsupported media provider")
        if provider == "Odysee":
            info = await self._odysee_info(link)
            direct_url = str((info or {}).get("url") or "")
            if not direct_url:
                raise RuntimeError("Odysee claim could not be resolved to a playable stream")
            from AquaVibe.utils.downloader import download_file
            from AquaVibe.core.dir import DOWNLOAD_DIR
            safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", title or "odysee")[:70] or "odysee"
            out = os.path.join(str(DOWNLOAD_DIR), safe + ".mp4")
            path = await download_file(direct_url, out)
            if not path:
                raise RuntimeError("Odysee direct CDN download failed")
            return path, False
        from AquaVibe.utils.downloader import media_download
        path = await media_download(link, type="video" if video else "audio", title=title or provider)
        if path and os.path.isfile(path) and os.path.getsize(path) > 16000:
            return str(path), False
        raise RuntimeError(f"{provider} full download failed")

    async def download(self, link: str, title: str = "", video: bool = False) -> Tuple[str, bool]:
        """Resolve a playable source without forcing a full media download.

        Returning a provider/CDN URL lets PyTgCalls/ffmpeg begin playback while
        the source is still being read. Full downloads are kept as a fallback
        for providers whose direct URL cannot be resolved reliably.
        """
        provider = self._provider(link)
        if not provider and self.is_direct_media(link):
            # Direct HTTP/HLS sources are already playable inputs for PyTgCalls.
            # Do not download the entire file before joining the voice chat.
            return str(link), True
        if not provider:
            raise RuntimeError("Unsupported media provider")

        # Odysee/LBRY exposes a public CDN URL; stream that URL directly.
        if provider == "Odysee":
            info = await self._odysee_info(link)
            if not info:
                raise RuntimeError("Odysee claim could not be resolved to a playable stream")
            direct_url = str(info.get("url") or "")
            if not direct_url:
                raise RuntimeError("Odysee returned no playable stream URL")
            return direct_url, True

        # Resolve a short-lived CDN URL first. A full provider download is only
        # used after direct playback itself fails.
        try:
            info = await self._yt_info(link)
            formats = info.get("formats") or []
            if video:
                candidates = [
                    f for f in formats
                    if f.get("url") and f.get("vcodec") not in (None, "none")
                    and f.get("acodec") not in (None, "none")
                ]
                selected = max(candidates, key=lambda f: ((f.get("height") or 0), (f.get("tbr") or 0))) if candidates else None
            else:
                candidates = [
                    f for f in formats
                    if f.get("url") and f.get("acodec") not in (None, "none")
                ]
                selected = max(candidates, key=lambda f: (f.get("abr") or 0, f.get("tbr") or 0)) if candidates else None
            direct_url = str((selected or {}).get("url") or "")
            if direct_url and not self.is_hls(direct_url):
                return direct_url, True
        except Exception as exc:
            log.warning("Direct provider stream resolution failed for %r: %s", link, exc)

        # Do not fall back to a full download here. If direct playback fails,
        # stream.py explicitly retries through download_full() so the assistant
        # never spends minutes idle in the VC before the first playback attempt.
        raise RuntimeError(f"{provider} has no direct playable stream URL")
