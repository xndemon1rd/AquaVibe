# Authored By Dev © 2025
from pyrogram.types import CallbackQuery
from pyrogram.enums import ChatType, ChatMemberStatus
from pyrogram.errors import ChannelPrivate, ChatAdminRequired, UserNotParticipant

# get_chat_member raises ChatAdminRequired whenever the *bot itself* isn't an
# admin in that chat (Telegram only lets admins query arbitrary participants
# in supergroups/channels via channels.GetParticipant) -- extremely common,
# since plenty of groups add the bot as a regular member. ChannelPrivate
# covers the bot having no access at all, UserNotParticipant covers a target
# who isn't actually in the chat. None of these mean the user is an admin,
# so we fail closed (False) instead of crashing every admin-gated command.
_MEMBER_LOOKUP_ERRORS = (ChannelPrivate, ChatAdminRequired, UserNotParticipant)


async def is_admin(message_or_cq) -> bool:
    if isinstance(message_or_cq, CallbackQuery):
        message = message_or_cq.message
    else:
        message = message_or_cq

    if not message.from_user:
        return False

    if message.chat.type not in [ChatType.SUPERGROUP, ChatType.CHANNEL, ChatType.GROUP]:
        return False

    if message.from_user.id in [777000, 1087968824]:
        return True

    client = message._client
    try:
        member = await client.get_chat_member(message.chat.id, message.from_user.id)
    except _MEMBER_LOOKUP_ERRORS:
        return False
    return member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]

async def is_group_owner(message_or_cq) -> bool:
    if isinstance(message_or_cq, CallbackQuery):
        message = message_or_cq.message
    else:
        message = message_or_cq

    if not message.from_user:
        return False

    if message.chat.type not in [ChatType.SUPERGROUP, ChatType.CHANNEL, ChatType.GROUP]:
        return False

    if message.from_user.id in [777000, 1087968824]:
        return True

    client = message._client
    try:
        member = await client.get_chat_member(message.chat.id, message.from_user.id)
    except _MEMBER_LOOKUP_ERRORS:
        return False
    return member.status == ChatMemberStatus.OWNER
