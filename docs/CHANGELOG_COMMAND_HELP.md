# Command help cards

Tapping a command in /help now opens a short card: what it does, usage, example, who can use it, and a tip.

- New: `AquaVibe/utils/command_help.py` holds one card per command (edit here to change text).
- Changed: `AquaVibe/plugins/bot/help.py` renders the card; old "All Commands" buttons (`noop_cmd:`) now work too.
- Fixed wrong help text: /speed (opens buttons, not a number), /mmf (meme text), group photo/title commands (now under Group Setup).

## Ranking
- New `/ranking` (also `/rankings`): tabs for Economy (coins), Songs Played and XP, top 10 per group plus your own position.
- New `AquaVibe/utils/play_stats.py`: real songs-played counter, called from `utils/stream/stream.py` on each play request. (`add_song_history` was never called before, so /history and /toptracks have no data.)
- Songs Played only counts plays from now on; Economy and XP use the existing data.

## Catalog + audit fixes
- Added 38 commands to the catalog (chess, elo, chesstop, uno, economy, rob/kill/shield/revive/topkill, romance, check-ins, group AI controls, channel-play and force-play aliases) with help cards.
- Fixed: `_social_cfg` was undefined in ai_social.py, so the AI group listener crashed on every group message.
- Fixed: UNO winner's ¥5,000 went to chat 0 (game record had no chat_id), so it never showed in the group.
- Fixed: /chesstop showed "Player" for everyone; /elo could crash on unknown users; inline "chess rapid" was ignored.
- Fixed: /shield hint told people to use `/protect @user` (that is the admin group-protection command).

## Games without the Mini App, currency, action limits
- **UNO in chat** (`plugins/social/uno_chat.py`, rules in `utils/uno_engine.py`): `/uno` opens a lobby (Join / Leave / Start). In game, the
  🃏 Play a card button opens Telegram inline mode and lists only YOUR playable cards (wilds list one entry per colour). Draw / Pass / My hand are
  normal buttons. Idle players are auto-skipped after `UNO_TURN_TIMEOUT` s and removed after two strikes. `/unoend` stops a game. Winner gets
  `UNO_WIN_REWARD` in the group wallet. **BotFather:** enable inline mode (`/setinline`) and inline feedback 100% (`/setinlinefeedback`).
- **UNO stickers (optional):** the bot cannot ship Telegram UNO sticker file_ids (they are per-bot). Owner replies to a sticker with
  `/unomap red 5` / `/unomap wild` / `/unomap wild4`; `/unomap status` shows progress. Mapped cards show as stickers in the picker, the rest as text cards.
  Needs a Pyrogram build that has `InlineQueryResultCachedSticker`; otherwise text cards are used.
- **Chess in chat** (`plugins/social/chess_chat.py`): the board is an inline keyboard. Tap a piece, then a highlighted square. Promotion picker,
  resign (with confirm), draw offer/accept, clocks with a "claim time" button, ELO with draws. `/chess [mode] [@user]` (reply or leave out @user for an open challenge).
  `@bot chess [blitz|rapid|unlimited]` inline quick-challenge (unrated). Mini App is no longer needed; the optional web server is untouched.
- **Currency**: one setting, `CURRENCY_SYMBOL` (default ¥), used through `utils/economy.py` by /balance, /give, /rob, /shield, /revive, /checkin, /ranking, UNO.
- **Action limits** (all in `.env`, defaults shown): /rob every 10 min, 5/day, victim immune 5 min after being robbed, victim needs 100+, steals at most 25% of their balance.
  /kill every 15 min, 5/day, knock-out 30 min. /shield costs 150, lasts 15 min, 30 min cooldown, 3/day; `/shield` alone shields yourself.
  /revive costs 200 and gives 5 min of protection. Knocked-out players cannot /rob, /kill or /shield.
- Fixed: check-in records were mixed up with rob/kill state records (same collection); balances can no longer go negative when robbed/paid at the same moment.
- Tested here: UNO rules + full simulated games, action limits, chess wiring (against a stand-in board). **Not tested:** the real bot on Telegram, and chess
  with the real `python-chess` library (not installable in the sandbox).
