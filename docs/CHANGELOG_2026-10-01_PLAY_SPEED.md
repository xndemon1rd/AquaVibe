# /play speed-up — 2026-10-01

Static changes only (bot not run; no network/credentials in the build sandbox).

- `utils/database.py`: `is_maintenance()` hit MongoDB on every /play and every admin command.
  Now cached for 5 s; `maintenance_on/off` clear the cache so toggles are instant.
- `utils/stream/stream.py`: `record_play` (stats upsert) runs in the background instead of
  blocking playback.
- `utils/decorators/play.py`: command-message delete runs in the background; `get_playmode` +
  `get_playtype` fetched together; assistant membership check (`get_chat_member`) cached 5 min
  after a good result (cache dropped on ban/restrict/UserNotParticipant).
- `plugins/play/play.py`: for `/play <name>` the YouTube search starts immediately and runs
  while the "processing" message is being sent.
- `platforms/Youtube.py`: `/vplay` no longer spawns a separate `yt-dlp --dump-json` (is_live)
  process before downloading — that was a second full YouTube extraction.
- `utils/downloader.py`: `check_formats=False`, `concurrent_fragment_downloads=4`; live streams
  are skipped via `match_filter` and fall back to the direct stream URL as before.
