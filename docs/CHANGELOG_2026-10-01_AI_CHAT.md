# 2026-10-01 - AI chatbot fix + upgrade

## Why it was not working
1. Gemini 2.5 Flash spends hidden "thinking" tokens from `maxOutputTokens`; with the 700-token chat cap the
   reply came back empty/cut off (MAX_TOKENS) -> every provider "failed" -> the bot stayed silent. Thinking is now off for chat.
2. Every failure was swallowed silently. Now logged, and the user (plus the owner with the real reason) is told.
3. Chat only worked in groups on @mention/reply - nothing in DMs, and `/ai` did not work in DMs. Both fixed.
4. Sticker-pack lookup used a pyrogram internal with the wrong signature, so it always failed and the bot just echoed the sticker.
   Replaced with a raw GetStickerSet + FileId build (works on pyrofork).
5. A single rejected reaction blocked reactions in that group for an hour; reactions never fired in DMs or on stickers.
   Now the chat's allowed-reaction list is read and only allowed emoji are used.

## New / improved
- Replies in DMs, on @mention, reply-to-bot, or when called by name ("aqua ..."); `/chatty` groups: joins in on its own.
- Better multilingual: per-message script/language hint (Devanagari, Arabic/Urdu, Bengali, Tamil, Telugu, Thai, CJK, Cyrillic, romanized Hinglish...).
- Cleaner memory (merged turns, bigger window), 1024-token replies, long answers split.
- Sticker -> sticker in DMs and on replies to the bot; random sticker replies in /chatty groups.
- More random reactions (defaults 20% / 40% direct, 10 s cooldown), keyword-aware, also on stickers and in DMs.
- Owner `/aistatus`: live test of every provider + current settings (listed in the Owner Panel of /help).
- Gemini errors now include the real HTTP message (quota / invalid key / model not found).
