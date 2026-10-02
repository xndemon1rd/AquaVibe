# AquaVibe Security-Hardened Build

This build was statically reviewed and hardened for obvious credential exposure, privacy leaks, and unsafe command execution.

## Changes

- Removed the `/phone` phone-number lookup plugin and its embedded third-party API credential.
- Removed all previously hard-coded third-party API credentials from source code.
- Moved optional provider credentials to environment variables in `.env.example`.
- Removed the automatic daily full-MongoDB backup by default. It is now opt-in with `AUTO_BACKUP_ENABLED=true`.
- Kept the manual `/backup` command owner-only.
- Disabled join/leave chat logging by default with `CHATLOG_ENABLED=false`; it no longer exports private invite links automatically.
- Removed third-party paste uploads from centralized error reporting. Large tracebacks are sent directly to the configured Telegram logger instead.
- Replaced the shell-based FFmpeg invocation in `core/call.py` with argument-based `create_subprocess_exec`, preventing shell metacharacters in media paths from becoming commands.
- Added `.gitignore` protections for `.env`, session files, logs, backups, caches, and playback artifacts.
- Added `.env.example` containing variable names only; no real credentials are included.
- Ran the repository's `validate_build.py` preflight successfully.

## Credentials

Any credentials that were present in the original source should be treated as exposed and rotated at their respective providers. This archive intentionally contains no replacement secret values.

## Notes

The project still supports Telegram assistant session strings because they are part of the music/voice-chat architecture. Only supply sessions you control, through environment variables; never commit them to source control.


## Hosting/runtime fix
- Added an explicit guard before selecting a voice assistant so an empty assistant list produces a clear configuration error instead of `IndexError: Cannot choose from an empty sequence`.
- Voice assistants are enabled by default because this is a music/voice bot; configure at least one valid `STRING_SESSION`.
- External media uploads remain enabled by default as requested; they can be disabled with `EXTERNAL_UPLOADS_ENABLED=false`.

## Advanced error system

- Error reporting is enabled by default when `LOGGER_ID` is configured.
- Errors receive stable fingerprints, severity, occurrence counts and built-in diagnosis/fix guidance.
- Structured JSONL error events are retained locally for host-side debugging.
- Duplicate/rate-limited failures are suppressed to prevent alert storms.
- Tracebacks and contexts are sanitized for common bot tokens, API keys/hashes, MongoDB URIs, bearer tokens and session strings before reporting.
- No arbitrary source-code rewriting or AI self-modification is performed.
