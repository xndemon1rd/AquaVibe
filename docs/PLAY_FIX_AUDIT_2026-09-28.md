# /play /vplay audit — 2026-09-28 (static analysis; bot not run)

## Root cause (why /play and /vplay did nothing in groups)
`plugins/misc/leaderboard.py` registered `@app.on_message(filters.group & ~filters.service)` in
Pyrogram handler group 0. Pyrogram runs only the FIRST matching handler per group, and plugins load
alphabetically (`misc` before `play`). The XP tracker matched every group message and never continued
propagation, so `play_command` (and ~60 other group-0 handlers loaded after it) never ran: no reply,
command message not deleted. Fix: `group=90`.

## Second blocker
`utils/decorators/play.py` used the old inverted maintenance check (`is False`) but `is_maintenance()`
now returns True when maintenance is ON. Every non-sudo user got "under maintenance" and the command
was never deleted. Fix: `if maintenance:` (fail open on DB error).

## Other confirmed bugs fixed
- `/start sudolist` -> TypeError (`admins_list(_=_)`); function takes (client, message).
- Playlist Audio/Video buttons used `AquaVibePlaylists`, handler listens for `SayaPlaylists`.
- /settings Language button `LANGUAGE_SETTINGS` had no handler (handler is `LG`).
- `LiveStream` button had no handler -> added `play_live_stream`.
- `filters.regex("LG")` unanchored -> could hijack callbacks whose id contains "LG"; now `^LG$`.
- `"f" if fplay else "d"` always "f" (fplay is a string) -> `fplay == "f"`.

## Confirmed, NOT fixed
- Vote-skip button `ADMIN  UpVote|` (decorators/admins.py) has no callback handler (NOT fixed; needs a real vote flow).

- Dead code: `aqua_search_markup` (AqPick/AqPage), legacy help markups in utils/inline/help.py.


- 12 modules import `db` from AquaVibe.misc, a name only created at runtime by `dbb()`.

## Round 2 fixes
- `-v` flag now only matches a standalone token (previously "/vplay spider-verse" or "x-vibes" flipped modes / mangled the query).
- `/start help...` deep link now opens the working help menu.
- 12 bare `except:` -> `except Exception:` (no longer swallow task cancellation).
