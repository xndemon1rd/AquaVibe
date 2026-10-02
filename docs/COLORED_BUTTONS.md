# AquaVibe coloured buttons (blue / green / red)

Code: `AquaVibe/utils/colored_buttons.py` (hooks installed in `AquaVibe/core/bot.py`).

| Colour | Telegram style | Typical buttons |
|--------|----------------|-----------------|
| Blue   | `primary`      | back, next, menu, help, info, queue, lyrics, settings, links |
| Green  | `success`      | play, pause, shuffle, loop, vplay, confirm, everything else |
| Red    | `danger`       | close, stop, cancel, delete, remove, mute, clear |

## Set a colour yourself
```python
InlineKeyboardButton("Stop", callback_data="x", color="red")   # "blue" | "green" | "red"
```
Without `color=`, the colour is picked automatically from the button text /
callback data (`pick_color()`); edit the word lists at the top of the module.

## How it works
Pyrofork cannot send Bot API 9.4 button styles, so the hooks send the keyboard
normally and then colour it through `editMessageReplyMarkup` in the background.
Keyboard-only refreshes (the player timer) go straight through the Bot API in a
single call so the buttons never flash grey. If the Bot API call fails, the
message and its buttons still work, just uncoloured.

Hooked Client methods: send_message, send_photo, send_video, send_audio,
send_animation, send_document, send_voice, edit_message_text,
edit_message_caption, edit_message_media, edit_message_reply_markup.

## Playback card image
`AquaVibe/assets/AquaVibe/playback_card.jpg`, exposed as `config.PLAYBACK_CARD_IMG`.
`PLAYLIST_IMG_URL`, `STREAM_IMG_URL`, `TELEGRAM_AUDIO_URL`, `TELEGRAM_VIDEO_URL`
and `SOUNCLOUD_IMG_URL` all point at it. Override with the `PLAYBACK_CARD_IMG`
env var (file path or https URL).

## Speed note (2026-09-30)
Colouring is a second request, so a slow connection shows up as buttons turning
coloured 1-2 s late. `colored_buttons.warm_up()` (called from `MusicBotClient.start`)
now opens the Bot API connection at startup and pings it every 45 s; the session is
IPv4-only with cached DNS and a 2.5 s connect timeout; a 429 wait is capped at 2 s.
