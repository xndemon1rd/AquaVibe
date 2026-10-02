# AquaVibe Command Audit

Static/offline audit of the hosting-fixed build. Live Telegram/Mongo/API testing still requires real credentials and services.

- Python files: **156**
- Files with command filters: **84**
- Unique command names: **196**
- `python -m compileall`: **PASS**
- `validate_build.py`: **PASS**
- `/sg`: guarded when no assistant is active; requires valid `STRING_SESSION` for live lookup.
- Assistant selection: empty-list guards in `set_assistant` and `set_calls_assistant`.
- `/couple`: fixed missing `upic.png` fallback by using bundled `couple.png`.

## Command files

- `AquaVibe/plugins/admin/botschk.py` — /botschk
- `AquaVibe/plugins/admin/admins.py` — /admins, /badmin, /dbadmin, /delalladmin, /rmadmin
- `AquaVibe/plugins/admin/post.py` — /post
- `AquaVibe/plugins/admin/restart.py` — /logs
- `AquaVibe/plugins/admin/logger.py` — /logger
- `AquaVibe/plugins/admin/gban.py` — /gban, /gbanlist, /gbannedusers, /globalban, /ungban
- `AquaVibe/plugins/admin/backup.py` — /backup
- `AquaVibe/plugins/admin/blchat.py` — /blacklistedchats, /blchat, /blchats, /unblacklistchat, /unblchat, /whitelistchat
- `AquaVibe/plugins/admin/block.py` — /block, /blocked, /blockedusers, /blusers, /unblock
- `AquaVibe/plugins/admin/maintenance.py` — /maintenance
- `AquaVibe/plugins/admin/autoend.py` — /autoend
- `AquaVibe/plugins/Manager/promote.py` — /demote, /fullpromote, /promote, /tempadmin
- `AquaVibe/plugins/Manager/info.py` — /info, /userinfo, /whois
- `AquaVibe/plugins/Manager/language.py` — /lang, /setlang
- `AquaVibe/plugins/Manager/vc_control.py` — /vstart
- `AquaVibe/plugins/Manager/del_msg.py` — /deleteall
- `AquaVibe/plugins/Manager/assisuser.py` — /assistantjoin, /leaveall, /userbotjoin, /userbotleave
- `AquaVibe/plugins/Manager/actions.py` — /ban, /dban, /kick, /kickme, /mute, /sban, /tban, /tmute, /unban, /unmute
- `AquaVibe/plugins/Manager/purge.py` — /del, /purge, /spurge
- `AquaVibe/plugins/Manager/id.py` — /id
- `AquaVibe/plugins/Manager/staff.py` — /bots, /staff
- `AquaVibe/plugins/Manager/grouphandler.py` — /pin, /removephoto, /setdiscription, /setphoto, /settitle, /unpin
- `AquaVibe/plugins/Manager/zombie.py` — /zombies
- `AquaVibe/plugins/misc/truth_dare.py` — /dare, /truth
- `AquaVibe/plugins/misc/ai_assistant.py` — /ai, /cimage
- `AquaVibe/plugins/misc/movie.py` — /movie
- `AquaVibe/plugins/misc/tts.py` — /tts, /voiceall, /voices
- `AquaVibe/plugins/misc/bored.py` — /bored
- `AquaVibe/plugins/misc/broadcast.py` — /bbcast
- `AquaVibe/plugins/misc/mongochk.py` — /mongochk
- `AquaVibe/plugins/misc/user_features.py` — /check, /history, /lyrics, /myhistory, /playlist
- `AquaVibe/plugins/misc/premium.py` — /bal, /banner, /coins, /daily, /economy, /hide, /membership, /profile, /refer, /setbanner1, /setbanner2, /setprofilebanner, /setprofilephoto, /shop, /store, /vip, /wallet, /weekly
- `AquaVibe/plugins/misc/urlshortner.py` — /short, /unshort
- `AquaVibe/plugins/tools/kang.py` — /kang
- `AquaVibe/plugins/tools/upscale.py` — /getdraw, /upscale
- `AquaVibe/plugins/tools/active.py` — /ac, /activevc
- `AquaVibe/plugins/tools/telegraph.py` — /telegraph, /tgm, /tgt
- `AquaVibe/plugins/tools/sticker.py` — /packkang, /stdl, /stickerid
- `AquaVibe/plugins/tools/mmf.py` — /mmf
- `AquaVibe/plugins/tools/invitelink.py` — /givelink, /invitelink, /link
- `AquaVibe/plugins/tools/couples.py` — /couple
- `AquaVibe/plugins/tools/group.py` — /leavegroup
- `AquaVibe/plugins/tools/reload.py` — /admincache, /reboot, /refresh, /reload
- `AquaVibe/plugins/tools/videoedit.py` — /extract
- `AquaVibe/plugins/tools/ping.py` — /ping
- `AquaVibe/plugins/tools/stats.py` — /dbstats, /gstats, /stats, /status
- `AquaVibe/plugins/tools/queue.py` — /player, /playing, /queue
- `AquaVibe/plugins/tools/bugs.py` — /bug
- `AquaVibe/plugins/tools/waifu.py` — /waifu
- `AquaVibe/plugins/tools/quote.py` — /q
- `AquaVibe/plugins/tools/speedtest.py` — /speedtest, /spt
- `AquaVibe/plugins/tools/imposter.py` — /imposter
- `AquaVibe/plugins/admins/pause.py` — /cpause, /pause
- `AquaVibe/plugins/admins/speed.py` — /playback, /slow, /speed
- `AquaVibe/plugins/admins/resume.py` — /cresume, /resume
- `AquaVibe/plugins/admins/stop.py` — /end
- `AquaVibe/plugins/admins/shuffle.py` — /cshuffle, /shuffle
- `AquaVibe/plugins/admins/seek.py` — /cseek, /cseekback, /seek, /seekback
- `AquaVibe/plugins/admins/totalmembers.py` — /user
- `AquaVibe/plugins/admins/skip.py` — /cnext, /cskip, /next, /skip
- `AquaVibe/plugins/admins/vcinfo.py` — /vcinfo, /vcmembers
- `AquaVibe/plugins/admins/loop.py` — /cloop, /loop
- `AquaVibe/plugins/admins/auth.py` — /auth, /authlist, /authusers, /unauth
- `AquaVibe/plugins/play/play.py` — /play, /vplay
- `AquaVibe/plugins/play/channel.py` — /channelplay
- `AquaVibe/plugins/play/playmode.py` — /mode, /playmode
- `AquaVibe/plugins/Kishu/wishcute.py` — /cute, /wish
- `AquaVibe/plugins/Kishu/meme.py` — /meme
- `AquaVibe/plugins/Kishu/love.py` — /love
- `AquaVibe/plugins/Kishu/hexacode.py` — /decode, /encode
- `AquaVibe/plugins/Kishu/domain.py` — /domain
- `AquaVibe/plugins/Kishu/qr.py` — /qr
- `AquaVibe/plugins/Kishu/ip.py` — /ip
- `AquaVibe/plugins/Kishu/dicegame.py` — /ball, /basket, /dart, /dice, /football, /jackpot
- `AquaVibe/plugins/Kishu/fonts.py` — /font
- `AquaVibe/plugins/Kishu/write.py` — /day, /write
- `AquaVibe/plugins/Kishu/weather.py` — /weather
- `AquaVibe/plugins/Kishu/bgremove.py` — /rmbg
- `AquaVibe/plugins/Kishu/groupdata.py` — /groupdata
- `AquaVibe/plugins/Kishu/sg.py` — /sg
- `AquaVibe/plugins/Kishu/pypi.py` — /pypi
- `AquaVibe/plugins/bot/settings.py` — /settings
- `AquaVibe/plugins/bot/help.py` — /help
- `AquaVibe/plugins/bot/start.py` — /start

## Testing boundary

A command can be syntax/registration-clean but still depend on Telegram permissions, MongoDB, assistant sessions, or third-party APIs. Those live integrations were not falsely marked as tested.
