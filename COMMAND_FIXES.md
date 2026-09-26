# Command fixes in this release

## /q
- Uses the replied message(s) in the correct chronological range.
- Quote service failures now produce a useful Telegram error instead of leaking a traceback.
- HTTPS certificate verification is enabled.
- Processing-message cleanup is guarded.

## /kang
- Raw sticker-set creation now converts the resolved peer to the `InputUser` type required by Telegram's sticker API.
- Sticker-pack bot username is sanitized and has a safe fallback.
- Existing media conversion and cleanup behavior is retained.

## Economy / VIP / Membership removal
- Removed the economy/VIP/membership plugin and its purchase/coin commands.
- Removed economy category and commands from help/catalog.
- Removed automatic daily/weekly coin rewards and referral attribution from `/start`.
- Profile storage remains intact because profile/photo/banner features still use the existing database storage layer.
