import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]
DRIVE_FOLDER_ID = os.environ["DRIVE_FOLDER_ID"]


def get_drive_service():
    creds_json = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(
        creds_json, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)


def upload_file(local_path, filename, subfolder_name=None):
    service = get_drive_service()
    parent = DRIVE_FOLDER_ID

    if subfolder_name:
        parent = get_or_create_subfolder(service, subfolder_name, DRIVE_FOLDER_ID)

    file_metadata = {"name": filename, "parents": [parent]}
    media = MediaFileUpload(local_path, resumable=True)
    uploaded = service.files().create(
        body=file_metadata, media_body=media, fields="id"
    ).execute()
    return uploaded.get("id")


def get_or_create_subfolder(service, name, parent_id):
    query = (
        f"name='{name}' and mimeType='application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents and trashed=false"
    )
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder.get("id")
