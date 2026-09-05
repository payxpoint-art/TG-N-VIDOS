import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from database import init_db, get_progress, upsert_progress
from drive_uploader import upload_file
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


@app.post("/start-backup/{channel_id}")
async def start_backup(channel_id: str):
    if channel_id in backup_tasks and not backup_tasks[channel_id].done():
        return {"status": "already_running"}
    task = asyncio.create_task(run_backup(int(channel_id)))
    backup_tasks[channel_id] = task
    return {"status": "started"}


@app.get("/status/{channel_id}")
async def status(channel_id: str):
    progress = get_progress(channel_id)
    return progress or {"status": "not_started"}


async def run_backup(channel_id: int):
    entity = await client.get_entity(channel_id)
    channel_name = getattr(entity, "title", str(channel_id))
    progress = get_progress(str(channel_id)) or {}
    last_id = progress.get("last_message_id", 0)

    upsert_progress(str(channel_id), channel_name=channel_name, status="running")

    videos = progress.get("total_videos", 0)
    photos = progress.get("total_photos", 0)
    files_ = progress.get("total_files", 0)
    failed = progress.get("total_failed", 0)

    async for message in client.iter_messages(entity, min_id=last_id, reverse=True):
        media_type = classify_media(message)
        if media_type:
            try:
                local_path = await message.download_media(file="downloads/")
                if local_path:
                    filename = os.path.basename(local_path)
                    upload_file(local_path, filename, subfolder_name=channel_name)
                    os.remove(local_path)

                    if media_type == "video":
                        videos += 1
                    elif media_type == "photo":
                        photos += 1
                    else:
                        files_ += 1
            except Exception as e:
                failed += 1
                print(f"Failed on message {message.id}: {e}")

        upsert_progress(
            str(channel_id),
            channel_name=channel_name,
            last_message_id=message.id,
            total_videos=videos,
            total_photos=photos,
            total_files=files_,
            total_failed=failed,
        )

    upsert_progress(str(channel_id), status="completed")
