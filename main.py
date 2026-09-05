from dotenv import load_dotenv
load_dotenv()  # .env file me daali gayi values ko environment me load karo

import os
import re
import asyncio
from datetime import timezone, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from telethon.tl.types import DocumentAttributeVideo

from database import (
    init_db, get_progress, upsert_progress, add_log,
    is_already_sent, mark_sent, get_all_progress,
)
from telegram_client import client, list_dialogs, classify_media, ensure_connected
from bot_control import start_bot

app = FastAPI()
templates = Jinja2Templates(directory="templates")
init_db()

os.makedirs("downloads", exist_ok=True)

CONCURRENCY = int(os.environ.get("CONCURRENCY", "5"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "5"))

COUNTER_KEY = {"video": "videos", "photo": "photos", "file": "files", "text": "texts"}

IST = timezone(timedelta(hours=5, minutes=30))

backup_tasks = {}  # channel_id -> asyncio task (in-memory tracker)


def format_ist(dt):
    if dt is None:
        return "unknown"
    return dt.astimezone(IST).strftime("%d %b %Y, %I:%M %p")


def build_caption(message):
    """Original caption bilkul waisi hi rakho, sirf neeche date aur ek
    chhota SRC_ID tag add karo (SRC_ID cross-account resume ke liye zaroori
    hai — isko destination channel se delete mat karna)."""
    original_caption = message.text or ""
    original_date = format_ist(message.date)
    lines = []
    if original_caption:
        lines.append(original_caption)
    lines.append(f"Original date: {original_date}")
    lines.append(f"SRC_ID:{message.id}")
    return "\n".join(lines)


def get_video_attr(message):
    """Original video ki exact properties (duration/width/height) nikalta
    hai taki destination pe bhi wahi ek normal playable video bane, file
    jaisa na lage — single tap se play ho jaye."""
    try:
        if message.media and getattr(message.media, "document", None):
            for attr in message.media.document.attributes:
                if isinstance(attr, DocumentAttributeVideo):
                    return DocumentAttributeVideo(
                        duration=attr.duration,
                        w=attr.w,
                        h=attr.h,
                        supports_streaming=True,
                        round_message=getattr(attr, "round_message", False),
                    )
    except Exception:
        pass
    return None


@app.on_event("startup")
async def startup():
    try:
        await ensure_connected()
    except Exception as e:
        # App crash nahi hoga — dashboard pe clear error dikhega, Railway
        # bar-bar restart (crash loop) nahi karega.
        print(f"STARTUP WARNING: {e}")
    asyncio.create_task(keep_alive_loop())
    asyncio.create_task(start_bot(trigger_backup))


async def keep_alive_loop():
    """Runs forever in background — pings Telegram every few minutes so the
    connection never sits idle long enough to get dropped."""
    while True:
        await asyncio.sleep(240)
        try:
            await ensure_connected()
            await client.get_me()
        except Exception as e:
            print(f"keep_alive ping failed: {e}")


def trigger_backup(source_id: int, dest_id: int):
    """Web dashboard aur Telegram bot dono isi function se backup start
    karte hain, taki dono jagah same logic use ho."""
    key = str(source_id)
    if key in backup_tasks and not backup_tasks[key].done():
        return False
    task = asyncio.create_task(run_backup(source_id, dest_id))
    backup_tasks[key] = task
    return True


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    try:
        dialogs = await list_dialogs()
    except RuntimeError as e:
        return HTMLResponse(f"<h3>{e}</h3>")
    return templates.TemplateResponse(
        "channels.html", {"request": request, "dialogs": dialogs}
    )


@app.get("/select-destination/{source_id}", response_class=HTMLResponse)
async def select_destination(request: Request, source_id: str):
    dialogs = await list_dialogs()
    return templates.TemplateResponse(
        "select_destination.html",
        {"request": request, "dialogs": dialogs, "source_id": source_id}
    )


@app.post("/start-backup/{source_id}/{dest_id}")
async def start_backup(source_id: str, dest_id: str):
    started = trigger_backup(int(source_id), int(dest_id))
    return {"status": "started" if started else "already_running"}


@app.get("/status/{channel_id}")
async def status(channel_id: str):
    progress = get_progress(channel_id)
    return progress or {"status": "not_started"}


async def recover_from_destination(dest_entity, channel_id_key):
    """Agar local DB khaali hai (naya Railway account/deployment), to
    destination channel ko khud scan karke last resume point nikaal lete
    hain — taki backup shuru se dobara na ho, duplicate na jaye."""
    recovered_last_id = 0
    try:
        async for msg in client.iter_messages(dest_entity, search="SRC_ID:", limit=1):
            text = msg.message or ""
            m = re.search(r"SRC_ID:(\d+)", text)
            if m:
                recovered_last_id = int(m.group(1))
    except Exception as e:
        print(f"recover last id failed: {e}")

    if recovered_last_id:
        add_log(
            channel_id_key,
            f"Naya deployment/account detect hua — destination channel se "
            f"purani progress mil gayi. Message id {recovered_last_id} ke "
            f"baad se continue hoga (duplicate nahi jayega)."
        )
    return recovered_last_id


async def process_unit(messages, dest_entity, sem, counters, channel_id_key):
    """Ek 'unit' process karta hai — ye ek single message ho sakta hai, ya
    ek poora album/group (jaise 5 videos ek saath bheji gayi thi source
    me). Group hamesha group me hi destination pe jayega, alag-alag nahi."""
    if all(is_already_sent(channel_id_key, m.id) for m in messages):
        return  # pura group/message pehle hi bheja ja chuka hai

    async with sem:
        try:
            await ensure_connected()

            media_msgs = [m for m in messages if classify_media(m)]
            text_msgs = [m for m in messages if not classify_media(m) and m.text]

            if media_msgs:
                paths = []
                for m in media_msgs:
                    p = await m.download_media(file="downloads/")
                    if p:
                        paths.append(p)
                        mtype = classify_media(m)
                        counters[COUNTER_KEY[mtype]] += 1

                if not paths:
                    raise RuntimeError("media download nahi hua")

                primary = media_msgs[0]
                caption = build_caption(primary)

                if len(paths) == 1:
                    kwargs = {}
                    video_attr = get_video_attr(primary)
                    if video_attr:
                        kwargs["attributes"] = [video_attr]
                    elif classify_media(primary) == "video":
                        kwargs["supports_streaming"] = True
                    await client.send_file(dest_entity, paths[0], caption=caption, **kwargs)
                else:
                    # Album/group — sab ek saath ek hi message group me jayenge
                    await client.send_file(
                        dest_entity, paths, caption=caption, supports_streaming=True
                    )

                for p in paths:
                    try:
                        os.remove(p)
                    except OSError:
                        pass

            for m in text_msgs:
                counters["texts"] += 1
                await client.send_message(dest_entity, build_caption(m))

            for m in messages:
                mark_sent(channel_id_key, m.id)

            ids = ",".join(str(m.id) for m in messages)
            tag = "group" if len(messages) > 1 else "msg"
            add_log(channel_id_key, f"OK {tag} [{ids}]: bhej diya")
        except Exception as e:
            counters["failed"] += 1
            ids = ",".join(str(m.id) for m in messages)
            add_log(channel_id_key, f"FAIL [{ids}]: {type(e).__name__}: {e}")


async def run_backup(source_id: int, dest_id: int):
    channel_id_key = str(source_id)
    await ensure_connected()
    source_entity = await client.get_entity(source_id)
    dest_entity = await client.get_entity(dest_id)
    source_name = getattr(source_entity, "title", str(source_id))
    dest_name = getattr(dest_entity, "title", str(dest_id))

    progress = get_progress(channel_id_key) or {}
    last_id = progress.get("last_message_id", 0)

    counters = {
        "videos": progress.get("total_videos", 0),
        "photos": progress.get("total_photos", 0),
        "files": progress.get("total_files", 0),
        "texts": progress.get("total_texts", 0),
        "failed": progress.get("total_failed", 0),
    }

    if last_id == 0:
        recovered_id = await recover_from_destination(dest_entity, channel_id_key)
        if recovered_id:
            last_id = recovered_id

    upsert_progress(
        channel_id_key,
        channel_name=source_name,
        destination_id=str(dest_id),
        destination_name=dest_name,
        status="running",
    )
    add_log(
        channel_id_key,
        f"Backup shuru: '{source_name}' -> '{dest_name}' (parallel workers: {CONCURRENCY})"
    )

    sem = asyncio.Semaphore(CONCURRENCY)
    units = []          # batch me flush hone wale units (message groups)
    current_group = []  # abhi collect ho raha album
    current_group_id = None

    async def flush_units():
        if not units:
            return
        await asyncio.gather(
            *[process_unit(u, dest_entity, sem, counters, channel_id_key) for u in units]
        )
        max_id = max(m.id for u in units for m in u)
        upsert_progress(
            channel_id_key,
            channel_name=source_name,
            last_message_id=max_id,
            total_videos=counters["videos"],
            total_photos=counters["photos"],
            total_files=counters["files"],
            total_texts=counters["texts"],
            total_failed=counters["failed"],
        )
        units.clear()

    async for message in client.iter_messages(source_entity, min_id=last_id, reverse=True):
        gid = message.grouped_id
        if gid is not None and gid == current_group_id:
            current_group.append(message)
            continue

        # naya message/group shuru ho raha hai — purana group band karo
        if current_group:
            units.append(current_group)

        if gid is not None:
            current_group = [message]
            current_group_id = gid
        else:
            units.append([message])
            current_group = []
            current_group_id = None

        if len(units) >= BATCH_SIZE:
            await flush_units()

    if current_group:
        units.append(current_group)
    await flush_units()

    upsert_progress(channel_id_key, status="completed")
    add_log(channel_id_key, "Backup completed.")
