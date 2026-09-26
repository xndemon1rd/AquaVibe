# AquaVibe — Feature Merge Notes

This build keeps AquaVibe's existing features and adds only missing high-value capabilities inspired by public Telegram-bot projects reviewed on GitHub.

## Added in this merge

- Advanced protection umbrella: `/protect`
- Raid protection with configurable join-rate trigger: `/raidmode`, `/raidstatus`
- Pending join-request controls: `/approve`, `/unapprove`
- Custom goodbye automation: `/setgoodbye`, `/goodbye`
- Recent bot-message cleanup: `/cleanup`
- Range purge helper: `/purgefrom`
- Clear all pins: `/unpinall`
- Help catalog synchronized with every registered command

## Existing AquaVibe systems intentionally preserved

Music/VC, provider resolution, playlists, AI, image generation, group moderation, CAPTCHA, warnings, anti-link, anti-flood, locks, notes, filters, AFK, reports, leaderboard/XP, economy, reminders, broadcast, backup, string-session generator, profiles, utilities and other existing commands were not duplicated.

## Source inspiration

Feature research included public projects such as TeamYukki/YukkiMusicBot, Alita Robot and other Telegram management/music bots. This merge uses the documented feature ideas and AquaVibe's own implementation rather than copying repository source wholesale.

- TeamYukki/YukkiMusicBot — MIT; documented music/VC, playlists, loop/seek/shuffle, live streams, multi-assistant configuration.
- Alita Robot — MIT; documented moderation, filters, notes, greetings, protection and backups.

Always review upstream licenses before copying code from third-party repositories into a distribution build.
