# Media startup latency fix — 2026-09-27

- Alternative-media playback now resolves a direct provider/CDN stream first instead of downloading the entire track before joining the voice chat.
- Direct HTTP/HLS sources are passed to PyTgCalls directly.
- Odysee resolved CDN media is passed through directly.
- yt-dlp provider formats are resolved to a playable direct URL before any full-download fallback.
- If direct playback fails, the stream path explicitly falls back to a full local download and retries.
- Added timing logs for media-source resolution so slow providers can be identified from Railway logs.

This prevents the assistant from sitting in the voice chat for the duration of a full media download before the first playback attempt.
