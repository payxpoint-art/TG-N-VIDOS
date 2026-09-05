import os
from telethon import TelegramClient
from telethon.sessions import StringSession
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


async def ensure_connected():
    """Call this before any Telegram API call — reconnects if the
    connection dropped due to idle timeout or network blip."""
    if not client.is_connected():
        await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError(
            "Telegram session not authorized. TG_SESSION_STRING check karo."
        )


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
