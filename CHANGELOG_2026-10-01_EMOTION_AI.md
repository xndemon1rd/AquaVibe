# 2026-10-01 — Emotional & sensitive chat AI, sticker-for-sticker

## New: `AquaVibe/utils/emotion_engine.py`
Reads every message before Aqua answers: emotion (joy, laugh, love, sadness, anger, fear, surprise, tired,
gratitude, apology, greeting), intensity, negation ("not happy"), sarcasm, caps/shouting, and a
**sensitivity level** (0 normal · 1 tender · 2 heavy · 3 crisis). English, Hinglish, Hindi, Urdu-roman,
basic Spanish and emoji. (The old detector used `\b` around emoji, so emoji never matched — fixed.)

## Sensitive replies
* **Crisis** (self-harm / suicide language): calm, warm, short reply in the user's language; no jokes,
  no stickers, no reactions, no lecturing; encourages a trusted person / local emergency number / crisis line.
  If every AI provider is down, a caring canned message is sent instead of "trouble thinking".
  Editable helplines: `CRISIS_LINES` in `emotion_engine.py`.
* **Heavy topics** (grief, illness, abuse, bullying): soft, present, no jokes, no stickers, no reactions.
* **Tender moods** (sad, stressed, angry, drained): acknowledge first, then support. Only a soft ❤/🤗 reaction.
* Crisis text is kept out of group history and out of long-term memory; a gentle check-in is scheduled for later.
* `/chatty` never jumps uninvited into a sad or serious message.

## More advanced chat
* Mood now decays back to baseline over time and reacts empathically to the user (PAD model).
* Relationship stage (new acquaintance → best friend) shapes warmth.
* Emotion trend over the last days ("has seemed low lately → check in softly").
* Follow-ups: "I have an exam tomorrow" → Aqua asks how it went the next time you chat.
* Style matching (short vs long messages, emoji use) and welcome-back after long silence.
* Better memory extraction (name, city, birthday, job/study, pets, favourites); serious messages are never stored.
* Rolling summary of long chats (`summary`), so context survives beyond 80 turns. `/forget` clears it.
* `/aimood`, `/airelationship` show the new state; **`/aiforgetme`** erases everything stored about you.

## Sticker with sticker
A sticker is answered with a sticker **that fits the feeling** (😭 → hug/comfort, 😂 → laugh, 😡 → calming, 😍 → love…).
It triggers when the sticker is: sent in a DM · a reply to the bot · a reply to a message that @mentions the bot ·
sent within `AI_STICKER_WINDOW` seconds after the user talked to the bot (and is not a reply to someone else).
Order: the user's own pack → owner packs → every sticker the bot has seen. Sad/angry/scared stickers are never
answered with a random or echoed sticker; if no fitting one exists Aqua answers with caring text instead.
Text replies can also carry a matching sticker (the model adds `[[sticker:joy]]`; the tag is stripped) —
never in a sensitive moment.

Owner command: `/aistickerpack` (reply to a sticker, or `/aistickerpack pack_name`, `list`, `remove name`).
Tip: add 1–3 emotion-rich packs so the bot has stickers for every feeling from day one.

## Reactions
Feeling-aware: none on grief/abuse/crisis/angry messages; the invalid 😭 reaction on sadness and other
non-standard emoji were removed.

## New environment variables (all optional)
| Variable | Default | Meaning |
|---|---|---|
| `AI_EMOTE_STICKER` | `true` | add a feeling-matched sticker to some text replies |
| `AI_EMOTE_STICKER_CHANCE` | `0.6` | chance when the AI itself asks for a sticker |
| `AI_STICKER_WINDOW` | `120` | seconds after talking to the bot in which a user's sticker gets a sticker back |
| `AI_STICKER_PACKS` | empty | comma-separated sticker pack short names for emotion replies |

## Notes
* In groups with BotFather privacy mode ON, Telegram only delivers replies-to-bot and @mentions; a loose sticker
  right after a mention needs privacy mode OFF (or bot admin).
* The bot is an AI companion, not a crisis service; the safety replies say so and point to real people.
