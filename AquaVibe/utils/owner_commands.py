"""Owner-only command catalogue used by the private Owner panel."""

OWNER_COMMANDS = {
    "badmin": "Add a user to the bot's trusted admin list. Owner only.",
    "dbadmin": "Remove a user from the bot's trusted admin list. Owner only.",
    "rmadmin": "Remove a user from the bot's trusted admin list. Owner only.",
    "delalladmin": "Remove all additional bot admins while keeping the owner.",
    "gban": "Globally ban a user from the bot. Use it with a replied user or user ID.",
    "globalban": "Alias of /gban; globally ban a user from the bot.",
    "ungban": "Remove a user from the global-ban list.",
    "gbannedusers": "Show the users currently on the global-ban list.",
    "gbanlist": "Alias of /gbannedusers; show global bans.",
    "post": "Publish a prepared post through the bot's owner posting tool.",
    "backup": "Create a bot/database backup using the configured backup system.",
    "bbcast": "Broadcast an owner message to the bot's served chats/users.",
    "leavegroup": "Make the bot leave a specified group. Owner only.",
    "setbanner1": "Set the first profile/banner asset. Owner only.",
    "setbanner2": "Set the second profile/banner asset. Owner only.",
    "leaveall": "Make the assistant leave groups where the owner requests it.",
}
