# 蒼響 — Music Sources

The removed legacy video provider is intentionally disabled. AquaVibe does not use its extraction, cookies, PO tokens, visitor-data tricks, or search.

## Active media sources

- PeerTube — federated/public search and playback.
- Odysee — public search and resolved playback URLs.
- Dailymotion — public search and playback.
- Vimeo — public search-page discovery and playback.
- Rumble — public search-page discovery and playback.
- SoundCloud — public search and playback.
- Direct public audio/video URLs.
- M3U8/HLS live streams.
- Telegram audio/video replies.
- Spotify metadata -> AquaVibe provider resolver.
- Apple Music metadata -> AquaVibe provider resolver.

FreeTube and NewPipe are clients/front-ends, not separate hosted catalogs, so they are not treated as backend providers.

## Playback policy

1. Search supported providers.
2. Rank title/artist matches.
3. Resolve a playable source.
4. Download/stream through the supported media path.
5. Send the resulting media to FFmpeg/PyTgCalls.
6. Do not play a weak/unresolved result merely to produce a response.
