import os
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import AuthKeyDuplicatedError
from telethon.tl.types import (
    MessageMediaPhoto, MessageMediaDocument, DocumentAttributeVideo
)

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION_STRING = os.environ.get("TG_SESSION_STRING", "")

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH,
    connection_retries=None,   # keep retrying forever instead of giving up
    retry_delay=2,
    auto_reconnect=True,
)

# Agar session permanently invalid (AuthKeyDuplicatedError) ho jaye, to
# bar-bar crash hone ki jagah ye flag set karke app ko zinda rakhte hain,
# taki dashboard pe clear error dikhe aur Railway "crash loop" na kare.
SESSION_INVALID = False
SESSION_ERROR_MESSAGE = ""


async def ensure_connected():
    """Call this before any Telegram API call — reconnects if the
    connection dropped due to idle timeout or network blip."""
    global SESSION_INVALID, SESSION_ERROR_MESSAGE

    if SESSION_INVALID:
        raise RuntimeError(SESSION_ERROR_MESSAGE)

    try:
        if not client.is_connected():
            await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError(
                "Telegram session not authorized. TG_SESSION_STRING check karo."
            )
    except AuthKeyDuplicatedError:
        SESSION_INVALID = True
        SESSION_ERROR_MESSAGE = (
            "TG_SESSION_STRING permanently invalid ho chuki hai (session ek "
            "sath 2 jagah use hui thi). Naya session generate_session.py "
            "chala ke banao aur .env me TG_SESSION_STRING update karo, fir "
            "redeploy karo."
        )
        raise RuntimeError(SESSION_ERROR_MESSAGE)


async def list_dialogs():
    await ensure_connected()
    dialogs = await client.get_dialogs()
    result = []
    for d in dialogs:
        if d.is_channel or d.is_group:
            result.append({"id": d.id, "name": d.name})
    return result


def classify_media(message):
    if not message.media:
        return None
    if isinstance(message.media, MessageMediaPhoto):
        return "photo"
    if isinstance(message.media, MessageMediaDocument):
        for attr in message.media.document.attributes:
            if isinstance(attr, DocumentAttributeVideo):
                return "video"
        return "file"
    return None
