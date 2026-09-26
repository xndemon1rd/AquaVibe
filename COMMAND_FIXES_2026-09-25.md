# Command fixes

- `/settitle`: accepts `/settitle New Title` or reply-to-text; keeps group-admin permission checks.
- `/tts`: now supports `/tts <text>` with `en-US-AriaNeural` by default, while preserving `/tts <voice_model> <text>` and `/voices <text>`.
- `/stickerid`: clearer reply-to-sticker validation.
- `/speedtest`: clearer network/provider failure handling.
- `/refresh` and `/reload`: restricted to group admins and retain the 3-minute cache guard.
- `/rmbg`: accepts photos and image documents and handles download failures cleanly; still requires `REMOVE_BG_API_KEY`.
- `/getdraw`: supports DeepAI when `DEEP_API` is configured and OpenAI image generation when `OPENAI_API_KEY` is configured; gives a clear configuration message otherwise.
- `/encode` and `/decode`: keep their existing behavior, and the default bot attribution is now `@aquavibebot`.
- Default `BOT_USERNAME`/`ASSUSERNAME` changed from the old `aqua vibewingbot` value to `aquavibebot`.

## Repository-wide error/bug diagnostics
- Added owner-only `/audit` (`/repoaudit`, `/errorscan`).
- Added `/runtimeerrors` (`/recenterrors`) for current-process runtime fingerprints.
- Static audit reports the exact file/line, detected problem, and recommended fix.
- Runtime error reports retain sanitized traceback + diagnosis + recommended fix.
- Startup runs the static audit after Telegram connects and writes `repo_audit_report.txt` / `repo_audit_report.json` without blocking startup.
