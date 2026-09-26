# Authored By Dev © 2025
import sys
from pyrogram import Client, errors
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message, CallbackQuery

import config
from ..log_config import LOGGER


# Compatibility shim for legacy Pyrogram-style ``quote=`` calls. Kurigram
# does not accept ``quote`` on Message.reply* methods; when a plugin passes it,
# translate quote=True to the portable reply_to_message_id argument instead.
def _apply_styled_markup(result, kwargs):
    """Apply Telegram Bot API 9.4 button styles after Pyrofork sends a message."""
    try:
        reply_markup = kwargs.get("reply_markup")
        from AquaVibe.utils.styled_buttons import has_styled_buttons, apply_colored_markup
        if reply_markup is not None and has_styled_buttons(reply_markup) and result is not None:
            token = getattr(config, "BOT_TOKEN", "")
            if token:
                return apply_colored_markup(result, token, reply_markup=reply_markup)
    except Exception:
        pass
    return None


def _install_markup_edit_compatibility():
    """Also style keyboards created/edited from callback and message methods."""
    for cls, method_names in (
        (Message, ("edit_reply_markup",)),
        (CallbackQuery, ("edit_message_reply_markup", "edit_message_text", "edit_message_caption")),
        (Client, ("edit_message_reply_markup", "edit_message_text", "edit_message_caption")),
    ):
        for method_name in method_names:
            original = getattr(cls, method_name, None)
            if original is None or getattr(original, "_aqua_style_edit", False):
                continue

            async def wrapped(self, *args, __original=original, **kwargs):
                # Client-level edit methods below perform the single style
                # upgrade. Do not style again from Message/CallbackQuery.
                return await __original(self, *args, **kwargs)

            wrapped._aqua_style_edit = True
            setattr(cls, method_name, wrapped)


def _install_reply_compatibility():
    method_names = (
        "reply", "reply_text", "reply_photo", "reply_audio", "reply_video",
        "reply_animation", "reply_document", "reply_voice", "reply_sticker",
        "reply_media_group", "reply_location", "reply_contact", "reply_poll",
        "reply_dice", "reply_venue", "edit_text", "edit_caption",
    )
    for method_name in method_names:
        original = getattr(Message, method_name, None)
        if original is None or getattr(original, "_trebel_reply_compat", False):
            continue

        async def compatible(self, *args, __original=original, **kwargs):
            if "quote" in kwargs:
                quote = kwargs.pop("quote")
                if quote and "reply_to_message_id" not in kwargs:
                    kwargs["reply_to_message_id"] = self.id
            if "disable_web_page_preview" in kwargs:
                disabled = kwargs.pop("disable_web_page_preview")
                if disabled and "link_preview_options" not in kwargs:
                    try:
                        from pyrogram.types import LinkPreviewOptions
                        kwargs["link_preview_options"] = LinkPreviewOptions(is_disabled=True)
                    except Exception:
                        pass
            # Styling is handled once at the Client-level send/edit hook.
            # Message.reply_* delegates to Client.send_* internally; styling
            # here as well caused two Bot API edits per message and visible
            # colour flicker/race conditions.
            return await __original(self, *args, **kwargs)

        compatible._trebel_reply_compat = True
        setattr(Message, method_name, compatible)


def _install_client_preview_compatibility():
    # Client-level calls such as app.send_message() also used the legacy
    # disable_web_page_preview flag in older plugins.
    for method_name in ("send_message", "edit_message_text", "edit_message_caption"):
        original = getattr(Client, method_name, None)
        if original is None or getattr(original, "_trebel_preview_compat", False):
            continue

        async def compatible_client(self, *args, __original=original, __method_name=method_name, **kwargs):
            if "disable_web_page_preview" in kwargs:
                disabled = kwargs.pop("disable_web_page_preview")
                if disabled and "link_preview_options" not in kwargs:
                    try:
                        from pyrogram.types import LinkPreviewOptions
                        kwargs["link_preview_options"] = LinkPreviewOptions(is_disabled=True)
                    except Exception:
                        pass
            result = await __original(self, *args, **kwargs)
            # Pyrofork 2.3.x cannot serialize Bot API 9.4 button styles.
            # Upgrade any AquaVibe styled markup through the Bot API after the
            # normal MTProto send/edit has succeeded.
            try:
                styled = _apply_styled_markup(result, kwargs)
                if styled is not None:
                    await styled
            except Exception:
                pass
            return result

        compatible_client._trebel_preview_compat = True
        setattr(Client, method_name, compatible_client)


_install_reply_compatibility()
_install_markup_edit_compatibility()
_install_client_preview_compatibility()
try:
    from AquaVibe.utils.premium_emoji import install_message_emoji_hooks
    install_message_emoji_hooks()
except Exception:
    pass

class MusicBotClient(Client):
    def __init__(self):
        super().__init__(
            name="蒼響",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            workers=16,
            max_concurrent_transmissions=5,
        )
        LOGGER(__name__).info("Bot client initialized.")

    def add_handler(self, handler, group=0):
        """Wrap every un-decorated Pyrogram handler so exceptions reach LOGGER GC."""
        callback = getattr(handler, "callback", None)
        if callback and not getattr(callback, "_trabel_error_capture", False) and not getattr(callback, "_trabel_global_capture", False):
            async def guarded(client, *args, __callback=callback, **kwargs):
                try:
                    return await __callback(client, *args, **kwargs)
                except Exception as exc:
                    from AquaVibe.utils.errors import report_exception
                    obj = args[0] if args else None
                    chat = getattr(getattr(obj, "chat", None), "id", "N/A")
                    user = getattr(getattr(obj, "from_user", None), "id", "N/A")
                    label = "Callback Handler Error" if obj and obj.__class__.__name__ == "CallbackQuery" else "Message Handler Error"
                    await report_exception(exc, label=label, extras={"Handler": getattr(__callback, "__name__", "unknown"), "Chat ID": chat, "User ID": user})
                    raise
            guarded._trabel_global_capture = True
            handler.callback = guarded
        return super().add_handler(handler, group)

    async def start(self):
        await super().start()
        me = await self.get_me()
        self.username, self.id = me.username, me.id
        self.name = f"{me.first_name} {me.last_name or ''}".strip()
        self.mention = me.mention

        if config.LOGGER_ID:
            try:
                await self.send_message(
                    config.LOGGER_ID,
                    (
                        f"<u><b>» {self.mention} ʙᴏᴛ sᴛᴀʀᴛᴇᴅ :</b></u>\n\n"
                        f"ɪᴅ : <code>{self.id}</code>\n"
                        f"ɴᴀᴍᴇ : {self.name}\n"
                        f"ᴜsᴇʀɴᴀᴍᴇ : @{self.username}"
                    ),
                )
            except (errors.ChannelInvalid, errors.PeerIdInvalid):
                LOGGER(__name__).warning("⚠️ Bot cannot access the log group/channel; continuing without Telegram logger.")
            except Exception as exc:
                LOGGER(__name__).warning(f"⚠️ Telegram log group unavailable; continuing. Reason: {type(exc).__name__}")

            try:
                member = await self.get_chat_member(config.LOGGER_ID, self.id)
                if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
                    LOGGER(__name__).warning("⚠️ Bot is not an admin in LOGGER_ID; Telegram logger may be limited.")
            except Exception as e:
                LOGGER(__name__).warning(f"⚠️ Could not check LOGGER_ID admin status; continuing: {type(e).__name__}")
        else:
            LOGGER(__name__).info("Telegram logger disabled (LOGGER_ID=0).")

        # Report dispatcher registration count so a deployment log can prove
        # that Telegram handlers were registered before polling began.
        try:
            groups = getattr(getattr(self, "dispatcher", None), "groups", None)
            if groups is not None and hasattr(groups, "values"):
                handler_count = sum(len(v) for v in groups.values())
                group_count = len(groups)
                LOGGER(__name__).info(
                    "Telegram update dispatcher ready; registered handlers: %s across %s groups",
                    handler_count, group_count,
                )
            else:
                LOGGER(__name__).warning(
                    "Telegram update dispatcher ready; handler registry could not be inspected."
                )
        except Exception:
            pass

        LOGGER(__name__).info(f"✅ Music Bot started as {self.name} (@{self.username})")
