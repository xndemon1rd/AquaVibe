# Authored By Dev © 2025
from io import BytesIO
import base64
import textwrap
from PIL import Image, ImageDraw, ImageFont
from pyrogram import Client, filters
from pyrogram.types import Message
from AquaVibe.core.runtime import app
from httpx import AsyncClient, Timeout

# -----------------------------------------------------------------
fetch = AsyncClient(
    http2=True,
    verify=True,
    headers={
        "Accept-Language": "id-ID",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) \
                       AppleWebKit/537.36 (KHTML, like Gecko) \
                       Chrome/107.0.0.0 Safari/537.36 Edge/107.0.1418.42",
    },
    timeout=Timeout(20),
)
# ------------------------------------------------------------------------
class QuotlyException(Exception):
    pass
# --------------------------------------------------------------------------
async def get_message_sender_id(ctx: Message):
    if ctx.forward_date:
        if ctx.forward_sender_name:
            return 1
        elif ctx.forward_from:
            return ctx.forward_from.id
        elif ctx.forward_from_chat:
            return ctx.forward_from_chat.id
        else:
            return 1
    elif ctx.from_user:
        return ctx.from_user.id
    elif ctx.sender_chat:
        return ctx.sender_chat.id
    else:
        return 1
# -----------------------------------------------------------------------------------------
async def get_message_sender_name(ctx: Message):
    if ctx.forward_date:
        if ctx.forward_sender_name:
            return ctx.forward_sender_name
        elif ctx.forward_from:
            return (
                f"{ctx.forward_from.first_name} {ctx.forward_from.last_name}"
                if ctx.forward_from.last_name
                else ctx.forward_from.first_name
            )
        elif ctx.forward_from_chat:
            return ctx.forward_from_chat.title
        else:
            return ""
    elif ctx.from_user:
        if ctx.from_user.last_name:
            return f"{ctx.from_user.first_name} {ctx.from_user.last_name}"
        else:
            return ctx.from_user.first_name
    elif ctx.sender_chat:
        return ctx.sender_chat.title
    else:
        return ""
# ---------------------------------------------------------------------------------------------------
async def get_custom_emoji(ctx: Message):
    if ctx.forward_date:
        return (
            ""
            if ctx.forward_sender_name
            or not ctx.forward_from
            and ctx.forward_from_chat
            or not ctx.forward_from
            else ctx.forward_from.emoji_status.custom_emoji_id
        )

    return ctx.from_user.emoji_status.custom_emoji_id if ctx.from_user else ""

# ---------------------------------------------------------------------------------------------------
async def get_message_sender_username(ctx: Message):
    if ctx.forward_date:
        if (
            not ctx.forward_sender_name
            and not ctx.forward_from
            and ctx.forward_from_chat
            and ctx.forward_from_chat.username
        ):
            return ctx.forward_from_chat.username
        elif (
            not ctx.forward_sender_name
            and not ctx.forward_from
            and ctx.forward_from_chat
            or ctx.forward_sender_name
            or not ctx.forward_from
        ):
            return ""
        else:
            return ctx.forward_from.username or ""
    elif ctx.from_user and ctx.from_user.username:
        return ctx.from_user.username
    elif (
        ctx.from_user
        or ctx.sender_chat
        and not ctx.sender_chat.username
        or not ctx.sender_chat
    ):
        return ""
    else:
        return ctx.sender_chat.username
# ------------------------------------------------------------------------
async def get_message_sender_photo(ctx: Message):
    if ctx.forward_date:
        if (
            not ctx.forward_sender_name
            and not ctx.forward_from
            and ctx.forward_from_chat
            and ctx.forward_from_chat.photo
        ):
            return {
                "small_file_id": ctx.forward_from_chat.photo.small_file_id,
                "small_photo_unique_id": ctx.forward_from_chat.photo.small_photo_unique_id,
                "big_file_id": ctx.forward_from_chat.photo.big_file_id,
                "big_photo_unique_id": ctx.forward_from_chat.photo.big_photo_unique_id,
            }
        elif (
            not ctx.forward_sender_name
            and not ctx.forward_from
            and ctx.forward_from_chat
            or ctx.forward_sender_name
            or not ctx.forward_from
        ):
            return ""
        else:
            return (
                {
                    "small_file_id": ctx.forward_from.photo.small_file_id,
                    "small_photo_unique_id": ctx.forward_from.photo.small_photo_unique_id,
                    "big_file_id": ctx.forward_from.photo.big_file_id,
                    "big_photo_unique_id": ctx.forward_from.photo.big_photo_unique_id,
                }
                if ctx.forward_from.photo
                else ""
            )
# ---------------------------------------------------------------------------------
    elif ctx.from_user and ctx.from_user.photo:
        return {
            "small_file_id": ctx.from_user.photo.small_file_id,
            "small_photo_unique_id": ctx.from_user.photo.small_photo_unique_id,
            "big_file_id": ctx.from_user.photo.big_file_id,
            "big_photo_unique_id": ctx.from_user.photo.big_photo_unique_id,
        }
    elif (
        ctx.from_user
        or ctx.sender_chat
        and not ctx.sender_chat.photo
        or not ctx.sender_chat
    ):
        return ""
    else:
        return {
            "small_file_id": ctx.sender_chat.photo.small_file_id,
            "small_photo_unique_id": ctx.sender_chat.photo.small_photo_unique_id,
            "big_file_id": ctx.sender_chat.photo.big_file_id,
            "big_photo_unique_id": ctx.sender_chat.photo.big_photo_unique_id,
        }
# ---------------------------------------------------------------------------------------------------
async def get_text_or_caption(ctx: Message):
    if ctx.text:
        return ctx.text
    elif ctx.caption:
        return ctx.caption
    else:
        return ""
# ---------------------------------------------------------------------------------------------------
async def local_quote_sticker(message):
    """Render a single replied message locally; no external quote service required."""
    text = await get_text_or_caption(message)
    text = (text or "").strip()
    if not text:
        text = "📎 Media"
    name = (await get_message_sender_name(message) or "Unknown").strip()
    username = (await get_message_sender_username(message) or "").strip()
    if username:
        name = f"{name}  @{username}"

    W, H = 512, 512
    pad = 34
    bg = (27, 20, 41)
    fg = (245, 242, 250)
    muted = (177, 168, 190)
    accent = (110, 82, 170)
    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
    ]
    bold_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
    ]
    def load_font(candidates, size):
        for f in candidates:
            try:
                return ImageFont.truetype(f, size)
            except OSError:
                continue
        return ImageFont.load_default()

    name_font = load_font(bold_candidates, 28)
    text_font = load_font(font_candidates, 25)
    small_font = load_font(font_candidates, 18)

    # Header accent
    draw.rounded_rectangle((pad, 34, W-pad, 42), radius=4, fill=accent)
    draw.text((pad, 68), name[:42], font=name_font, fill=fg)
    draw.text((pad, 108), "AQUA VIBE • QUOTE", font=small_font, fill=muted)

    # Wrap to the available width and cap the total height for sticker-safe output.
    max_chars = 31
    lines = []
    for paragraph in text.splitlines() or [text]:
        lines.extend(textwrap.wrap(paragraph, width=max_chars, break_long_words=True, break_on_hyphens=False) or [""])
    max_lines = 11
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = (lines[-1][:max_chars-1] + "…")

    y = 158
    line_h = 35
    for line in lines:
        draw.text((pad, y), line, font=text_font, fill=fg)
        y += line_h

    # Footer / subtle message id marker (no raw IDs exposed to users)
    draw.text((pad, H-48), "made with AquaVibe", font=small_font, fill=muted)

    out = BytesIO()
    out.name = "aqua_quote_sticker.webp"
    img.save(out, format="WEBP", quality=92, method=6)
    out.seek(0)
    return out

async def pyrogram_to_quotly(messages, is_reply):
    if not isinstance(messages, list):
        messages = [messages]
    payload = {
        "type": "quote",
        "format": "png",
        "backgroundColor": "#1b1429",
        "messages": [],
    }
# ------------------------------------------------------------------------------------------------------------
    for message in messages:
        the_message_dict_to_append = {}
        if message.entities:
            the_message_dict_to_append["entities"] = [
                {
                    "type": entity.type.name.lower(),
                    "offset": entity.offset,
                    "length": entity.length,
                }
                for entity in message.entities
            ]
        elif message.caption_entities:
            the_message_dict_to_append["entities"] = [
                {
                    "type": entity.type.name.lower(),
                    "offset": entity.offset,
                    "length": entity.length,
                }
                for entity in message.caption_entities
            ]
        else:
            the_message_dict_to_append["entities"] = []
        the_message_dict_to_append["chatId"] = await get_message_sender_id(message)
        the_message_dict_to_append["text"] = await get_text_or_caption(message)
        the_message_dict_to_append["avatar"] = True
        the_message_dict_to_append["from"] = {}
        the_message_dict_to_append["from"]["id"] = await get_message_sender_id(message)
        the_message_dict_to_append["from"]["name"] = await get_message_sender_name(
            message
        )
        the_message_dict_to_append["from"][
            "username"
        ] = await get_message_sender_username(message)
        the_message_dict_to_append["from"]["type"] = message.chat.type.name.lower()
        the_message_dict_to_append["from"]["photo"] = await get_message_sender_photo(
            message
        )
        if message.reply_to_message and is_reply:
            the_message_dict_to_append["replyMessage"] = {
                "name": await get_message_sender_name(message.reply_to_message),
                "text": await get_text_or_caption(message.reply_to_message),
                "chatId": await get_message_sender_id(message.reply_to_message),
            }
        else:
            the_message_dict_to_append["replyMessage"] = {}
        payload["messages"].append(the_message_dict_to_append)
    try:
        # Use the documented JSON endpoint first. It is more robust than relying
        # on a format-specific proxy path; decode the returned base64 image.
        r = await fetch.post("https://quote.yuri.ly/quote/generate", json=payload)
        content_type = (r.headers.get("content-type") or "").lower()
        if r.status_code == 200:
            if "application/json" in content_type:
                data = r.json()
                image_b64 = data.get("image")
                if image_b64:
                    return base64.b64decode(image_b64)
                raise QuotlyException(f"Quotly API error: {data.get('error') or 'no image returned'}")
            if r.content and ("image/" in content_type or r.content[:4] == b"RIFF"):
                return r.content

        detail = r.text[:300] if r.text else f"HTTP {r.status_code}"
        raise QuotlyException(f"Quotly service returned {detail}")
    except Exception as exc:
        if isinstance(exc, QuotlyException):
            raise
        raise QuotlyException(f"Quote service unavailable: {type(exc).__name__}") from exc
# ------------------------------------------------------------------------------------------

# Helper function to check if an argument is an integer
def isArgInt(txt) -> list:
    count = txt
    try:
        count = int(count)
        return [True, count]
    except ValueError:
        return [False, 0]

# ---------------------------------------------------------------------------------------------------
@app.on_message(filters.command("q") & filters.reply)
async def msg_quotly_cmd(self: Client, ctx: Message):
    # /q converts ONLY the message being replied to into a sticker.
    # No extra messages, ranges, or nested reply blocks are included.
    processing_msg = await ctx.reply_text("❄️")
    try:
        target_message = ctx.reply_to_message
        # Local renderer is the primary path: /q must not depend on an
        # unreliable third-party Quotly endpoint.
        bio_sticker = await local_quote_sticker(target_message)
        await ctx.reply_sticker(bio_sticker)
    except QuotlyException as e:
        await ctx.reply_text(f"❌ Quote service error: <code>{str(e)[:350]}</code>")
    except Exception as e:
        await ctx.reply_text(f"❌ Quote failed: <code>{type(e).__name__}</code>")
    finally:
        try:
            await processing_msg.delete()
        except Exception:
            pass
# ---------------------------------------------------------------------------------
