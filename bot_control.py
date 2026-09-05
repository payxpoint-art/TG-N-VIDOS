import os
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import MessageNotModifiedError

from telegram_client import list_dialogs
from database import get_progress

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("TG_OWNER_ID", "0") or "0")

bot = TelegramClient(StringSession(), API_ID, API_HASH) if BOT_TOKEN else None

# Owner ki current selection state (source select -> destination select)
_state = {}


def _is_owner(event):
    return OWNER_ID and event.sender_id == OWNER_ID


async def start_bot(trigger_backup_fn):
    """trigger_backup_fn(source_id:int, dest_id:int) -> bool (started ya nahi)"""
    if not bot:
        print("TG_BOT_TOKEN nahi diya — Telegram bot control disabled hai, "
              "sirf web dashboard use hoga.")
        return
    if not OWNER_ID:
        print("TG_OWNER_ID nahi diya — bot kisi ko bhi respond nahi karega. "
              "Apna numeric Telegram ID @userinfobot se lekar TG_OWNER_ID me daalo.")
        return

    await bot.start(bot_token=BOT_TOKEN)
    print("Telegram bot control connected.")

    @bot.on(events.NewMessage)
    async def handler(event):
        if not _is_owner(event):
            return

        text = (event.raw_text or "").strip()

        if text in ("/start", "/channels"):
            await _send_channel_list(event, stage="source")
            return

        if text == "/status":
            await _send_status(event)
            return

        if text.isdigit():
            await _handle_number(event, int(text), trigger_backup_fn)
            return

        await event.respond(
            "Commands:\n"
            "/channels — apne groups/channels ki list dekho (backup start karne ke liye)\n"
            "/status — chal rahe backups ka summary dekho"
        )


async def _send_channel_list(event, stage):
    dialogs = await list_dialogs()
    mapping = {}
    lines = []
    for i, d in enumerate(dialogs, start=1):
        mapping[i] = {"id": d["id"], "name": d["name"]}
        lines.append(f"{i}. {d['name']}")

    _state[OWNER_ID] = {"stage": stage, "map": mapping}

    if stage == "source":
        header = "Kis channel/group ka BACKUP LENA hai? Uska number bhejo:"
    else:
        header = "Kis channel/group me backup BHEJNA hai (DESTINATION)? Uska number bhejo:"

    await event.respond(header + "\n\n" + "\n".join(lines))


async def _handle_number(event, number, trigger_backup_fn):
    state = _state.get(OWNER_ID)
    if not state or number not in state["map"]:
        await event.respond("Pehle /channels bhejo list dekhne ke liye.")
        return

    if state["stage"] == "source":
        source = state["map"][number]
        dialogs = await list_dialogs()
        mapping = {}
        lines = []
        for i, d in enumerate(dialogs, start=1):
            mapping[i] = {"id": d["id"], "name": d["name"]}
            lines.append(f"{i}. {d['name']}")
        _state[OWNER_ID] = {"stage": "dest", "source": source, "map": mapping}
        await event.respond(
            f"Source select ho gaya: '{source['name']}'\n\n"
            "Ab DESTINATION channel ka number bhejo:\n\n" + "\n".join(lines)
        )
        return

    if state["stage"] == "dest":
        source = state["source"]
        dest = state["map"][number]
        started = trigger_backup_fn(source["id"], dest["id"])
        _state.pop(OWNER_ID, None)

        if started:
            status_msg = await event.respond(
                f"Backup shuru ho gaya:\n'{source['name']}' -> '{dest['name']}'\n\n"
                f"Neeche yahi message update hota rahega (live progress)..."
            )
            asyncio.create_task(_watch_progress(status_msg, str(source["id"])))
        else:
            await event.respond(
                f"'{source['name']}' ka backup pehle se chal raha hai. "
                f"/status bhejo progress dekhne ke liye."
            )
        return


def _format_progress_text(channel_name, dest_name, p):
    return (
        f"'{channel_name}' -> '{dest_name}'\n\n"
        f"Videos: {p.get('total_videos', 0)}\n"
        f"Photos: {p.get('total_photos', 0)}\n"
        f"Files: {p.get('total_files', 0)}\n"
        f"Texts: {p.get('total_texts', 0)}\n"
        f"Failed: {p.get('total_failed', 0)}\n"
        f"Status: {p.get('status')}"
    )


async def _watch_progress(status_msg, channel_id_key):
    """Har 8 second me ek hi message ko edit karta hai (naya message
    bhejta nahi) jab tak backup complete na ho jaye."""
    last_text = None
    while True:
        await asyncio.sleep(8)
        p = get_progress(channel_id_key)
        if not p:
            continue
        text = _format_progress_text(
            p.get("channel_name", ""), p.get("destination_name", ""), p
        )
        if text != last_text:
            try:
                await status_msg.edit(text)
                last_text = text
            except MessageNotModifiedError:
                pass
            except Exception:
                pass
        if p.get("status") == "completed":
            break


async def _send_status(event):
    from database import get_all_progress
    rows = get_all_progress()
    if not rows:
        await event.respond("Koi backup abhi tak start nahi hua.")
        return

    lines = []
    for r in rows:
        lines.append(_format_progress_text(
            r.get("channel_name", ""), r.get("destination_name", ""), r
        ))
    await event.respond("\n\n---\n\n".join(lines))
