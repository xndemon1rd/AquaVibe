# Audit & fixes — 2026-10-01

## Removed
- `/cock`, `/horny`, `/sexy`, `/hot` and `/boob` commands and every reference to them: handler registration, GIF/template entries
  (`plugins/tools/masti.py`), help cards (`utils/command_help.py`), help category lists (`plugins/bot/help.py`),
  the command catalog (`utils/command_catalog.py`), the fun-help text (`strings/helpers.py`) and the changelog.

## Fixed
- `/unpinall` was registered twice (`Manager/advanced_security.py` and `Manager/mass_actions.py`). The first one
  won and skipped the Yes/No confirmation that the help text promises. The duplicate was removed.
- `mass_actions`: crashed with `AttributeError` when the bot was not an admin (`privileges` is `None`); now replies
  with a clear message. Anonymous admins (no `from_user`) also get a clear reply instead of a crash.
- `masti` percentage commands (`/cutie /gay /lesbian`): a dead GIF/MP4 link or an anonymous sender
  made the command fail silently. Now falls back to a plain text reply and handles missing users.
  Media is sent with `send_animation` so it plays inline.
- `AquaVibe/misc.py`: `db` is now a stable module-level dict (was created only when `dbb()` ran, so
  `from AquaVibe.misc import db` depended on import order).
- `AquaVibe/__main__.py`: f-strings reused the same quote type inside `{}` (only valid on Python 3.12+); made portable.
- `strings/__init__.py`: language files were loaded via a CWD-relative path; now resolved from the package location.

## Verified
- All 199 Python files compile; `validate_build.py` passes.
- No undefined names, unresolved internal imports or shadowed handler functions.
- Every command in the catalog has a registered handler; language files parse and all used string keys exist.
- Plugin import smoke test (third-party libs stubbed): no import-time errors.

## Inline mode
- Removed the music search result from inline mode (`plugins/bot/inline.py`). That result is what showed the
  default "Annie Robot / Powered by" banner image as its thumbnail and preview.
- Removed the play-related text shortcuts (`/pause /resume /skip /end /shuffle /loop`) and the old "Whisper" hint
  article; `utils/inlinequery.py` was deleted because nothing else used it.
- Inline mode now serves: whispers, `@bot chess [mode]` and `@bot uno`. Any other query gets an empty answer, and
  a failure in the inline router is logged instead of breaking the handler.
- Router fix: the chess/UNO branches used to `return` even when they did not match, so a whisper that merely started
  with "chess" or "uno" could never reach the whisper handler. Each handler now falls through when it returns False.

## Whisper (rebuilt, `plugins/social/whisper.py`)
Type in any chat: `@bot @user your message`, `@bot your message @user`, `@bot whisper @a @b message`
(up to 5 recipients), `@bot whisper 123456789 message` (by numeric id), with options after the recipients:
`+30m` / `+2h` / `+1d` (expiry, default 24h, max 7d) and `!burn` (each recipient can read it once).
- Chat only shows "Private whisper for @user" plus Open / Delete buttons; the text is never in the chat.
- Text shows as a private popup (<= 190 chars) or, for longer whispers (up to 1000 chars), in the bot's private chat
  as a protected message that deletes itself after 60 s.
- Drafts live in memory only. A whisper is written to MongoDB only when it is sent or first opened, and only
  encrypted (Fernet, key from `WHISPER_SECRET` or derived from `BOT_TOKEN`). Without the `cryptography` package
  whispers stay memory-only instead of being stored as plaintext.
- Recipients are bound to their numeric id when the username resolves, so a reused username can't hijack a whisper.
- The sender sees how many people tried to open it; the sender can delete it any time; everything expires (Mongo TTL).
- Fixes made while integrating: wired the whisper into the inline router, per-whisper locks so burn-after-reading
  cannot be read twice by a double tap, a "burned" state on the chat message, deep-link errors are now logged instead
  of hidden, and dead code was removed.
- Optional: enable inline feedback in BotFather (`/setinlinefeedback`) so a whisper is saved the moment it is sent.
- New requirement: `cryptography` (added to `requirements.txt`). New optional env var: `WHISPER_SECRET`.
- The old `aqua_whispers` collection from the first implementation is no longer used (new data is in `aqua_whispers_v2`).
