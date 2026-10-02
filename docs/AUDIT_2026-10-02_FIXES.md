# Audit fixes — 2026-10-02

1. **Private-chat commands blocked** — `session_generator_input` matched every private text message in group 0, so Pyrogram never reached handlers registered after it: /speedtest /spt /stats /stickerid /stdl /packkang /tgm /telegraph /upscale /getdraw /extract /waifu. It now only matches while a /string session is active (other commands keep working mid-session; /skip still goes to the generator).
2. **Player buttons had no permission check** — anyone in the chat could press Pause/Skip/Stop/Loop/Shuffle/Replay/Volume. Controls now use `ActualAdminCB` (same rules as the /pause /skip ... commands, respects /playmode). Queue / Lyrics / Help buttons stay public.
3. **Vote button did nothing** — `ADMIN  UpVote|…` had no handler (vote mode is ON by default). Added `upvote_callback`; when the vote count is reached the action runs.
4. **/botschk** built a second assistant session from the same STRING and stopped it afterwards. It now reuses the running assistant, only starts/stops it if it wasn't already connected, and handles `from_user is None`.
5. **waifufxn** crashed on anonymous/channel senders or replies to them; `bored` removed from its table (misc/bored.py already owns /bored).
6. **Help / command catalog** listed commands with no handler: coins, economy, hide, membership, profile, shop, store, wallet, weekly (+ gstats, fonts, setbanner). Removed or corrected.

## Follow-up (same day)

7. **Language files completed** — every language now has all 289 keys that `en.yml` has. Added `H_B_30` and `vc_ended` (all languages), `S_B_5` (hinglish) and the 13 `server_*` strings (ru). Previously these silently fell back to English.
8. **Placeholder bugs in strings** — `hinglish` and `bhojpuri` `start_5` / `help_1` had lost their `{1}` / `{2}` / `{0}` links, so the sudo and support links never appeared. Restored.
9. **/unblock crashed in Bhojpuri** — `block_4` contained `{0MEL}` instead of `{0}`, so `.format()` raised `KeyError`. Fixed.
10. **Dead code removed** — `aqua_search_markup` (its `AqPick` / `AqPage` buttons had no handlers and nothing called it).

Static re-check after all changes: compile OK, `validate_build.py` PASS, no broken imports, no missing config names, no missing or mismatched language placeholders. The only items the checker still prints (`x`, `k`, `v`, `last_checked_time`) are false positives: comprehension variables and a `global` declared before assignment.
