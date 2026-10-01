# Gender-first /start + male welcome image
- First-time private /start asks "What is your gender, boss?" with [Male] [Female].
- After choosing, the welcome card is sent immediately (no second /start needed).
- Male: image = `AquaVibe/assets/welcome_male.jpg`. Female: image = `AquaVibe/assets/welcome_female.jpg`. Not set: original GIF. Caption + buttons unchanged.
- Saved gender can't be flipped by tapping old buttons.

# Command catalogue (Help) redesign
- New home screen: title, command count, one-line blurb per category, 2-column category buttons.
- Categories: Music, Channel & VC, AI Studio, Tools, Profile, Economy, Fun & Games, Moderation, Group Setup (+ More if anything is left over). Every command appears exactly once.
- Category pages: bold header, `/command — short description` list in a quote block (12 per page, prev/next), tap a command for description + usage + tips.
- Owner/sudo-only commands (gban, logs, reboot, blocklists, ...) are hidden from normal users and live in the Owner Panel; the Owner button is only shown to the owner (help + start panel).
- Fixed: Help/Menu buttons crashed when the welcome message was an animation/GIF (only photos were handled); "Menu" now restores the same welcome caption as /start.
- Group `/help` now opens the command center in private chat instead of editing the group message.
