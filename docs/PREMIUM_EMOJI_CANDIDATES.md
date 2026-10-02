# Emoji you can still convert to Telegram Premium (custom) emoji

Scanned every `.py` and `strings/*.yml` file. "Uses" = how many times the emoji appears in the code.

- Distinct emoji used: **305**
- Already mapped to a premium ID: **52**
- **Not mapped yet: 253**

To convert one: get its custom-emoji ID (forward the premium emoji to an ID bot such as @idstickerbot), then add a line to `DEFAULT_EMOJI` in `AquaVibe/core/premium_emoji.py`:

```python
"🔥": 1234567890123456789,
```

Notes:
- Premium emoji only render in messages built with `custom_emoji_entities()` (start, help, ping today).
- Emoji inside button labels need `icon_custom_emoji_id` on the button instead.
- Decorative symbols like ➻ ➠ ◆ ✯ © are plain text characters, not emoji, so they are left out.

## Not mapped yet (most used first)

| Emoji | Uses | Main files |
|---|---|---|
| ⚠ | 38 | bot.py, promote.py, group_management_extra.py |
| 🎄 | 37 | ar.yml, ru.yml, hi.yml |
| ✔ | 23 | vip_coding.py, ar.yml, ru.yml |
| 👤 | 17 | info.py, help.py, user_features.py |
| 🔗 | 16 | urlshortner.py, colored_buttons.py, group_management_extra.py |
| ❄ | 16 | ar.yml, ru.yml, hi.yml |
| ⏳ | 16 | chess_chat.py, social_features.py, mass_actions.py |
| 🚫 | 15 | social_features.py, invitelink.py, colored_buttons.py |
| 👀 | 15 | chess_chat.py, uno_chat.py, self_healing.py |
| 📝 | 14 | nobara_yukki_fun.py, community_tools_extra.py, colored_buttons.py |
| ♟ | 13 | chess_chat.py |
| 🍂 | 11 | ar.yml, ru.yml, hi.yml |
| 📎 | 10 | telegraph.py, bgremove.py, quote.py |
| 😲 | 10 | ar.yml, ru.yml, hi.yml |
| 🚨 | 9 | advanced_security.py, errors.py, self_healing.py |
| 📌 | 9 | chatlog.py, errors.py, advanced_security.py |
| 🔐 | 9 | session_generator.py, self_healing.py, start.py |
| 📹 | 9 | callback.py, ai_assistant.py, play.py |
| 🛡 | 9 | social_features.py, staff.py, advanced_security.py |
| 🎵 | 8 | inline.py, user_features.py, config.py |
| 🎯 | 8 | dicegame.py, nobara_yukki_fun.py, helpers.py |
| 📋 | 8 | callback.py, colored_buttons.py, errors.py |
| 👑 | 8 | vip_coding.py, errors.py, chess_chat.py |
| 📦 | 8 | backup.py, help.py, vip_coding.py |
| 🔎 | 8 | community_tools_extra.py, callback.py, start.py |
| ⏱ | 8 | chess_chat.py, info.py, vip_coding.py |
| ❓ | 8 | info.py, nobara_yukki_fun.py, ip.py |
| ⏰ | 8 | nobara_yukki_fun.py, ar.yml, ru.yml |
| 🔍 | 7 | vip_coding.py, config.py, info.py |
| 📚 | 7 | help.py, helpers.py, en.yml |
| ✖ | 7 | chess_chat.py, session_generator.py, colored_buttons.py |
| 🔄 | 7 | uno_engine.py, welcome.py, assisuser.py |
| ▶ | 7 | callback.py, uno_chat.py, playback_card.py |
| ⏭ | 7 | uno_chat.py, queue.py, play.py |
| 👋 | 7 | advanced_security.py, waifufxn.py, community_tools_extra.py |
| 💰 | 7 | vip_coding.py, ai_social.py, social_features.py |
| ⚡ | 6 | config.py, premium_emoji.py, help.py |
| 🎲 | 6 | dicegame.py, help.py, helpers.py |
| ⚙ | 6 | social_features.py, colored_buttons.py, ai_social.py |
| 💎 | 6 | vip_coding.py, welcome.py, help.py |
| 🎉 | 6 | nobara_yukki_fun.py, welcome.py, leaderboard.py |
| 🏆 | 6 | leaderboard.py, ai_social.py, chess_chat.py |
| 🎤 | 6 | callback.py, user_features.py |
| 📂 | 6 | ar.yml, ru.yml, hi.yml |
| 🔥 | 5 | masti.py, config.py, leaderboard.py |
| 🔇 | 5 | colored_buttons.py, play.py, group_management_extra.py |
| 🔊 | 5 | tts.py, colored_buttons.py, play.py |
| ☑ | 5 | info.py, backup.py |
| 💔 | 5 | social_features.py, en.yml |
| 🎳 | 4 | dicegame.py, helpers.py |
| ⚽ | 4 | dicegame.py, helpers.py |
| 🎰 | 4 | dicegame.py, helpers.py |
| ♡ | 4 | helpers.py, hinglish.yml, tr.yml |
| 📄 | 4 | nobara_yukki_fun.py, __main__.py, audit.py |
| 💬 | 4 | errors.py, id.py, social_features.py |
| 📜 | 4 | user_features.py, errors.py, social_features.py |
| 👥 | 4 | playback_card.py, vcinfo.py, start.py |
| 📊 | 4 | start.py, nobara_yukki_fun.py, groupdata.py |
| 💸 | 4 | social_features.py, ai_social.py |
| ⚪ | 4 | chess_chat.py |
| ⚫ | 4 | chess_chat.py |
| ⬜ | 4 | nobara_yukki_fun.py, chess_chat.py |
| ☠ | 4 | social_features.py |
| 🎴 | 4 | uno_chat.py |
| 🎨 | 4 | ai_assistant.py, upscale.py |
| 🪧 | 4 | imposter.py |
| 🔴 | 3 | __main__.py, uno_engine.py, audit.py |
| 🟡 | 3 | __main__.py, uno_engine.py, audit.py |
| ⛔ | 3 | uno_engine.py, colored_buttons.py |
| ⏹ | 3 | colored_buttons.py, queue.py, callback.py |
| ⬅ | 3 | play.py, colored_buttons.py |
| ℹ | 3 | colored_buttons.py, ip.py, videoedit.py |
| 🧾 | 3 | colored_buttons.py, play.py, callback.py |
| 📍 | 3 | errors.py, playback_card.py, self_healing.py |
| 🔁 | 3 | errors.py, play.py, callback.py |
| 🎚 | 3 | playback_card.py, vcinfo.py, callback.py |
| ⭐ | 3 | welcome.py, leaderboard.py, movie.py |
| ⏸ | 3 | queue.py, play.py, callback.py |
| ↩ | 3 | id.py, chess_chat.py, leaderboard.py |
| 😅 | 3 | social_features.py, actions.py |
| 🔓 | 3 | imposter.py, group_management_extra.py |
| 🎭 | 3 | info.py, movie.py, imposter.py |
| 💀 | 3 | social_features.py, nobara_yukki_fun.py |
| 😉 | 3 | waifufxn.py, couples.py, group.py |
| 🇮🇳 | 3 | hi.yml, hinglish.yml, bhojpuri.yml |
| ♪ | 2 | config.py, ping.py |
| 🟠 | 2 | __main__.py, audit.py |
| ◁ | 2 | colored_buttons.py, play.py |
| ▷ | 2 | colored_buttons.py, play.py |
| 🔙 | 2 | colored_buttons.py, vip_coding.py |
| 🛠 | 2 | errors.py, vip_coding.py |
| 🐍 | 2 | errors.py, session_generator.py |
| 🟢 | 2 | uno_engine.py, chess_chat.py |
| 🔵 | 2 | uno_engine.py, audit.py |
| 🔔 | 2 | uno_engine.py, uno_chat.py |
| 📁 | 2 | self_healing.py, backup.py |
| 💡 | 2 | self_healing.py, help.py |
| Ⓜ | 2 | font_styles.py |
| 🔧 | 2 | welcome.py, videoedit.py |
| ✚ | 2 | start.py |
| 🕒 | 2 | speed.py, ip.py |
| 🕛 | 2 | speed.py, backup.py |
| 🔀 | 2 | play.py, callback.py |
| 🚀 | 2 | backup.py, vip_coding.py |
| ⎋ | 2 | botschk.py |
| 📥 | 2 | advanced_security.py, user_features.py |
| 🧹 | 2 | advanced_security.py, ai_social.py |
| 🎙 | 2 | vc_control.py, group.py |
| 💤 | 2 | community_tools_extra.py |
| 📢 | 2 | community_tools_extra.py, start.py |
| 💥 | 2 | actions.py, waifufxn.py |
| 🌊 | 2 | group_management_extra.py |
| 📆 | 2 | info.py, write.py |
| ♘ | 2 | chess_chat.py |
| ♗ | 2 | chess_chat.py |
| ♖ | 2 | chess_chat.py |
| ♕ | 2 | chess_chat.py |
| 🏳 | 2 | chess_chat.py, ip.py |
| 📈 | 2 | chess_chat.py, chatlog.py |
| 😄 | 2 | chess_chat.py, waifufxn.py |
| 🔪 | 2 | social_features.py |
| 😭 | 2 | social_features.py |
| 👉 | 2 | uno_chat.py, waifufxn.py |
| 🛑 | 2 | uno_chat.py, nobara_yukki_fun.py |
| 🎶 | 2 | help.py |
| 💖 | 2 | leaderboard.py |
| 🤷 | 2 | bored.py, waifufxn.py |
| 🪨 | 2 | nobara_yukki_fun.py |
| ✂ | 2 | nobara_yukki_fun.py |
| 🤜 | 2 | nobara_yukki_fun.py |
| 🟩 | 2 | nobara_yukki_fun.py |
| 🟨 | 2 | nobara_yukki_fun.py |
| 🤗 | 2 | waifufxn.py |
| 😘 | 2 | waifufxn.py |
| 😊 | 2 | waifufxn.py |
| 💨 | 2 | waifufxn.py, weather.py |
| 🗣 | 2 | tts.py |
| 🔱 | 2 | vip_coding.py |
| 🔢 | 2 | vip_coding.py, ip.py |
| 💳 | 2 | vip_coding.py |
| 🍑 | 2 | wishcute.py, masti.py |
| 🗺 | 2 | ip.py |
| ⌛ | 2 | session_generator.py |
| ✧ | 2 | chatlog.py |
| 🐻‍❄ | 2 | imposter.py |
| 🎩 | 1 | config.py |
| 🥃 | 1 | config.py |
| 🧨 | 1 | config.py |
| 😁 | 1 | helpers.py |
| 😜 | 1 | helpers.py |
| ✘ | 1 | colored_buttons.py |
| 🗑 | 1 | colored_buttons.py |
| ⏪ | 1 | colored_buttons.py |
| ⏩ | 1 | colored_buttons.py |
| 🚦 | 1 | errors.py |
| 😎 | 1 | command_help.py |
| ➊ | 1 | font_styles.py |
| ➋ | 1 | font_styles.py |
| ➌ | 1 | font_styles.py |
| ➍ | 1 | font_styles.py |
| ➎ | 1 | font_styles.py |
| ➏ | 1 | font_styles.py |
| ➐ | 1 | font_styles.py |
| ➑ | 1 | font_styles.py |
| ➒ | 1 | font_styles.py |
| 💊 | 1 | welcome.py |
| 🕓 | 1 | speed.py |
| 🕤 | 1 | speed.py |
| ⏮ | 1 | play.py |
| ✕ | 1 | play.py |
| 🌹 | 1 | admins.py |
| 🗂 | 1 | backup.py |
| ⏲ | 1 | botschk.py |
| 👟 | 1 | actions.py |
| 🗓 | 1 | info.py |
| 🌠 | 1 | info.py |
| ♙ | 1 | chess_chat.py |
| ♔ | 1 | chess_chat.py |
| ♞ | 1 | chess_chat.py |
| ♝ | 1 | chess_chat.py |
| ♜ | 1 | chess_chat.py |
| ♛ | 1 | chess_chat.py |
| ♚ | 1 | chess_chat.py |
| ⬛ | 1 | chess_chat.py |
| 🤫 | 1 | social_features.py |
| 🥷 | 1 | social_features.py |
| 💚 | 1 | social_features.py |
| 🖤 | 1 | social_features.py |
| 🙋 | 1 | uno_chat.py |
| 🚪 | 1 | uno_chat.py |
| ▫ | 1 | uno_chat.py |
| 🖥 | 1 | vcinfo.py |
| 🥳 | 1 | callback.py |
| 🫠 | 1 | callback.py |
| 🔉 | 1 | callback.py |
| ♂ | 1 | start.py |
| ♀ | 1 | start.py |
| ✓ | 1 | start.py |
| 🐾 | 1 | start.py |
| 🔨 | 1 | help.py |
| 🚧 | 1 | help.py |
| 🏅 | 1 | leaderboard.py |
| 💠 | 1 | leaderboard.py |
| 🎬 | 1 | movie.py |
| 😐 | 1 | bored.py |
| 😔 | 1 | nobara_yukki_fun.py |
| 😒 | 1 | waifufxn.py |
| 😈 | 1 | waifufxn.py |
| 🙌 | 1 | waifufxn.py |
| 🔫 | 1 | waifufxn.py |
| 💃 | 1 | waifufxn.py |
| 😡 | 1 | waifufxn.py |
| 👍 | 1 | waifufxn.py |
| 👎 | 1 | waifufxn.py |
| 🍴 | 1 | waifufxn.py |
| 😋 | 1 | waifufxn.py |
| 😪 | 1 | waifufxn.py |
| 🤦 | 1 | waifufxn.py |
| 😆 | 1 | waifufxn.py |
| 😏 | 1 | waifufxn.py |
| ◀ | 1 | tts.py |
| 🥇 | 1 | ranking.py |
| 🥈 | 1 | ranking.py |
| 🥉 | 1 | ranking.py |
| ➡ | 1 | vip_coding.py |
| 🩹 | 1 | vip_coding.py |
| 📨 | 1 | vip_coding.py |
| 📷 | 1 | qr.py |
| 🌡 | 1 | weather.py |
| 🥵 | 1 | weather.py |
| 💧 | 1 | weather.py |
| ☁ | 1 | weather.py |
| 🏙 | 1 | ip.py |
| 📮 | 1 | ip.py |
| 🏢 | 1 | ip.py |
| 🖌 | 1 | bgremove.py |
| 🔷 | 1 | session_generator.py |
| 📩 | 1 | session_generator.py |
| 🎞 | 1 | videoedit.py |
| 🛰 | 1 | chatlog.py |
| 🍆 | 1 | masti.py |
| ⬆ | 1 | telegraph.py |
| 🔕 | 1 | group.py |
| 🍊 | 1 | imposter.py |
| 🍅 | 1 | imposter.py |
| 🍜 | 1 | imposter.py |
| 🍓 | 1 | imposter.py |
| 🚏 | 1 | imposter.py |
| 🍕 | 1 | imposter.py |
| 🇸🇦 | 1 | ar.yml |
| 🇷🇺 | 1 | ru.yml |
| 🇹🇷 | 1 | tr.yml |
| 🇺🇸 | 1 | en.yml |

## Already mapped

❌ ×147, ✅ ×52, 🥀 ×50, ✨ ×26, 🤖 ×23, 🔒 ×20, 💗 ×19, 🦋 ×9, 🪽 ×9, 🫧 ×8, 🧠 ×8, 💞 ×6, 😴 ×6, 🌐 ×6, 🌍 ×6, 🤝 ×6, 💕 ×6, 💍 ×6, 🎧 ×6, 🏠 ×6, 📅 ×6, 🤔 ×6, ↝ ×6, ↜ ×6, 🏓 ×6, 🕚 ×6, 😫 ×6, 🙂 ×6, 🧪 ×5, 💌 ×5, 🏀 ×5, 🧩 ×5, 🌈 ×4, 🕊 ×4, 🪄 ×4, 🎁 ×4, 🍷 ×3, 🥰 ×3, ❤ ×3, 📡 ×3, 🥂 ×2, 🌸 ×2, 💜 ×2, 🍒 ×2, 🧸 ×2, 📞 ×2, ✍ ×2, 💋 ×2, 🫶 ×2, 🤍 ×1, 📫 ×1, ⌨ ×1
