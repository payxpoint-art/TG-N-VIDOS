import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from database import init_db, get_progress, upsert_progress, add_log
from telegram_client import client, list_dialogs, classify_media

app = FastAPI()
templates = Jinja2Templates(directory="templates")
init_db()

os.makedirs("downloads", exist_ok=True)

backup_tasks = {}  # channel_id -> asyncio task (in-memory tracker)


@app.on_event("startup")
async def startup():
    await client.connect()
    if not await client.is_user_authorized():
        print("WARNING: Telegram session not authorized. "
              "Run generate_session.py locally first and set TG_SESSION_STRING.")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if not await client.is_user_authorized():
        return HTMLResponse(
            "<h3>Telegram session not authorized. Check Railway logs and "
            "make sure TG_SESSION_STRING is set correctly.</h3>"
        )
    dialogs = await list_dialogs()
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


async def run_backup(source_id: int, dest_id: int):
    channel_id_key = str(source_id)
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
    add_log(channel_id_key, f"Backup shuru: '{source_name}' -> '{dest_name}'")

    videos = progress.get("total_videos", 0)
    photos = progress.get("total_photos", 0)
    files_ = progress.get("total_files", 0)
    failed = progress.get("total_failed", 0)

    async for message in client.iter_messages(source_entity, min_id=last_id, reverse=True):
        media_type = classify_media(message)
        if media_type:
            try:
                local_path = await message.download_media(file="downloads/")
                if local_path:
                    caption = message.text or ""
                    await client.send_file(
                        dest_entity, local_path, caption=caption
                    )
                    os.remove(local_path)

                    if media_type == "video":
                        videos += 1
                    elif media_type == "photo":
                        photos += 1
                    else:
                        files_ += 1
                    add_log(
                        channel_id_key,
                        f"OK msg {message.id}: {media_type} bhej diya"
                    )
            except Exception as e:
                failed += 1
                add_log(
                    channel_id_key,
                    f"FAIL msg {message.id}: {type(e).__name__}: {e}"
                )

        upsert_progress(
            channel_id_key,
            channel_name=source_name,
            last_message_id=message.id,
            total_videos=videos,
            total_photos=photos,
            total_files=files_,
            total_failed=failed,
        )

    upsert_progress(channel_id_key, status="completed")
    add_log(channel_id_key, "Backup completed.")
