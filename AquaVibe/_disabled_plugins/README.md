# Disabled plugins

Files here are intentionally **not** loaded. `AquaVibe/plugins/__init__.py`
auto-discovers every `*.py` file under `AquaVibe/plugins/*/*.py`, so anything
that should stay off has to live outside that folder.

- `premium.py` — the economy/coins/VIP/membership/Telegram-Stars-store
  plugin. `ECONOMY_REMOVED.md` and `COMMAND_FIXES.md` in the repo root both
  already say this was removed (commands like `/coins`, `/bal`, `/wallet`,
  `/store`, `/vip`, `/membership`, `/daily`, `/weekly`, `/refer` were meant to
  be gone), but the file itself was left inside `plugins/misc/`, so the
  loader kept picking it up and every one of those commands was still live.
  Moved here so the code isn't lost — delete this folder if you're sure you
  don't want it, or move the file back under `plugins/<folder>/` to
  re-enable it (it will need `AquaVibe/utils/database.py`'s economy/profile
  helpers, which are still present and unaffected by this move).
