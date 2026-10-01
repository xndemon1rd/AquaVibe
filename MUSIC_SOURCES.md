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

# Aqua Search Engine (SayaMusicAPI-compatible aggregator)
SAYA_MUSIC_API_URL=https://sayamusicapi.shnwazdeveloperx.workers.dev

## Aqua Search Engine (Saya-style)

AquaVibe now uses a central SayaMusicAPI-compatible search engine rather than treating individual catalogues as separate user-facing search systems.

- Primary aggregator: `SAYA_MUSIC_API_URL` (defaults to the public SayaMusicAPI deployment).
- Primary search: `/v1/search/tracks?q=...`.
- Secondary fan-out: Saya provider adapters for Apple/iTunes, MusicBrainz, Deezer, Audius, JioSaavn, and related catalogues when the aggregate result set is thin or low-confidence.
- Local ranking: normalized title/artist matching, exact phrase preference, token overlap, duration/year signals, and playable-source preference.
- Search UI: 3 results per Telegram panel with pagination; selection is required for ambiguous matches.
- Playback: only legal preview/open/free streams exposed by the engine are eligible; the engine does not bypass DRM, paywalls, or protected full-track systems.
- `/vplay`: uses the same search/ranking session, then resolves a video stream only after the user selects a result.
