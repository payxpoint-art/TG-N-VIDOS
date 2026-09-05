import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from database import (
    init_db, get_progress, upsert_progress, add_log,
    is_already_sent, mark_sent,
)
from telegram_client import client, list_dialogs, classify_media, ensure_connected

app = FastAPI()
templates = Jinja2Templates(directory="templates")
init_db()

os.makedirs("downloads", exist_ok=True)

# Kitne messages ek saath (parallel) process honge.
# 4-5 safe hai. Zyada karoge to Telegram "flood wait" laga sakta hai.
CONCURRENCY = int(os.environ.get("CONCURRENCY", "5"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "5"))

LABELS = {"video": "Video", "photo": "Photo", "file": "File"}
COUNTER_KEY = {"video": "videos", "photo": "photos", "file": "files"}

backup_tasks = {}  # channel_id -> asyncio task (in-memory tracker)


@app.on_event("startup")
async def startup():
    await ensure_connected()
    asyncio.create_task(keep_alive_loop())


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
    key = source_id
    if key in backup_tasks and not backup_tasks[key].done():
        return {"status": "already_running"}
    task = asyncio.create_task(run_backup(int(source_id), int(dest_id)))
    backup_tasks[key] = task
    return {"status": "started"}


@app.get("/status/{channel_id}")
async def status(channel_id: str):
    progress = get_progress(channel_id)
    return progress or {"status": "not_started"}


async def process_one(message, dest_entity, sem, counters, channel_id_key):
    """Ek message download + send karta hai.
    - Agar ye message pehle hi safaltapoorvak bheja ja chuka hai (dedup
      table check), to skip kar deta hai — isse restart hone par duplicate
      upload nahi hote.
    - Caption me ek counting number bhi jodta hai (Video #12, Photo #5, etc)
      jo continue hota hai chahe tool beech me restart ho jaye.
    """
    media_type = classify_media(message)
    if not media_type:
        return

    if is_already_sent(channel_id_key, message.id):
        return  # pehle se bheja hua hai, dobara mat bhejo

    async with sem:
        try:
            await ensure_connected()

            # Number turant reserve kar lo (send hone se pehle) taki parallel
            # workers me bhi har item ko unique number mile.
            key = COUNTER_KEY[media_type]
            counters[key] += 1
            serial_number = counters[key]

            original_caption = message.text or ""
            label = LABELS[media_type]
            caption = f"{label} #{serial_number}"
            if original_caption:
                caption += f"\n{original_caption}"

            local_path = await message.download_media(file="downloads/")
            if local_path:
                await client.send_file(dest_entity, local_path, caption=caption)
                os.remove(local_path)
                mark_sent(channel_id_key, message.id)
                add_log(
                    channel_id_key,
                    f"OK msg {message.id}: {label} #{serial_number} bhej diya"
                )
            else:
                counters["failed"] += 1
                add_log(channel_id_key, f"FAIL msg {message.id}: media download nahi hua")
        except Exception as e:
            counters["failed"] += 1
            add_log(channel_id_key, f"FAIL msg {message.id}: {type(e).__name__}: {e}")


async def run_backup(source_id: int, dest_id: int):
    channel_id_key = str(source_id)
    await ensure_connected()
    source_entity = await client.get_entity(source_id)
    dest_entity = await client.get_entity(dest_id)
    source_name = getattr(source_entity, "title", str(source_id))
    dest_name = getattr(dest_entity, "title", str(dest_id))

    progress = get_progress(channel_id_key) or {}
    last_id = progress.get("last_message_id", 0)

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

    counters = {
        "videos": progress.get("total_videos", 0),
        "photos": progress.get("total_photos", 0),
        "files": progress.get("total_files", 0),
        "failed": progress.get("total_failed", 0),
    }

    sem = asyncio.Semaphore(CONCURRENCY)
    batch = []

    async def flush_batch():
        if not batch:
            return
        await asyncio.gather(
            *[process_one(m, dest_entity, sem, counters, channel_id_key) for m in batch]
        )
        max_id = max(m.id for m in batch)
        upsert_progress(
            channel_id_key,
            channel_name=source_name,
            last_message_id=max_id,
            total_videos=counters["videos"],
            total_photos=counters["photos"],
            total_files=counters["files"],
            total_failed=counters["failed"],
        )
        batch.clear()

    async for message in client.iter_messages(source_entity, min_id=last_id, reverse=True):
        batch.append(message)
        if len(batch) >= BATCH_SIZE:
            await flush_batch()

    await flush_batch()

    upsert_progress(channel_id_key, status="completed")
    add_log(channel_id_key, "Backup completed.")
