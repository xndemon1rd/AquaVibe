# AquaVibe Group Management Extras

Added missing group-management features without replacing AquaVibe's existing moderation/music handlers.

### Added commands
- `/warn`, `/warnings`, `/unwarn`, `/clearwarnings`, `/setwarnlimit`
- `/rules`, `/setrules`, `/setwelcome`
- `/report`
- `/antilink on|off`
- `/addbadword`, `/removebadword`, `/badwords`
- `/flood on|off`, `/setfloodlimit`
- `/lock all|links|media|stickers|gifs|photos|videos|audio|documents`
- `/unlock ...`
- `/captcha on|off`

### Protection
- Per-group MongoDB settings
- Warning counter with configurable auto-mute threshold
- Link and bad-word deletion for non-admins
- Optional flood detection with temporary mute
- Optional join CAPTCHA with 120-second verification
- Per-group rules and custom welcome template (`{name}`, `{group}`)
- Reply-based admin reports

AquaVibe's existing `/ban`, `/unban`, `/mute`, `/unmute`, `/tmute`, `/kick`, `/tban`, `/pin`, `/unpin`, `/purge`, `/promote`, `/demote`, mass actions and other existing group commands remain unchanged.
