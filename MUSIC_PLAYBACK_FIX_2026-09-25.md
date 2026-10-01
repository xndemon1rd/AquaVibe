# AquaVibe Music Playback Fix — 2026-09-25

## What was fixed

- Added SoundCloud search to the unified alternative-provider search path.
- Added direct public media URL recognition for common audio/video extensions.
- Added explicit M3U8/HLS handling so playlist URLs are streamed instead of sent to the file downloader.
- Added a provider-download fallback that resolves a playable yt-dlp format and downloads that format when the normal download path fails.
- Strengthened search scoring so exact/multi-token title matches receive substantially higher priority.
- Kept the removed legacy video provider disabled; no cookies, PO tokens, or legacy-provider search are added.
- Kept Spotify/Apple Music as metadata/resolver inputs rather than direct audio sources.

## Playback path

`/play` / `/vplay` -> provider search/resolution -> playable media validation/download -> FFmpeg/PyTgCalls -> voice chat.

For M3U8/HLS, the path is direct stream playback rather than file download.

## Validation

- Python compilation is run over the changed playback modules before packaging.
- The ZIP is checked to ensure the removed phone lookup plugin is not reintroduced.
