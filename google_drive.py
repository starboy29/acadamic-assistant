# google_drive.py

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
from config import ROOT_FOLDER_NAME

SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'credentials.json'

credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=credentials)

# Optional: manually set root folder ID or let it be created dynamically


def upload_file_to_drive(file_bytes, filename, category, subject, chapter=None, status="Pending"):
    """
    Uploads file to Google Drive in correct structured folder based on category.
    For Assignments: /Assignments/Pending|Completed/Subject
    For Notes/Exam Papers: /Category/Subject/Chapter
    """
    # Step 1: Start from shared root folder
    root_id = ROOT_FOLDER_NAME

    if category == "Assignments":
        # /Assignments/Pending/Subject
        status_folder_id = get_or_create_folder(status, get_or_create_folder("Assignments", root_id))
        subject_folder_id = get_or_create_folder(subject, status_folder_id)
        parent_id = subject_folder_id
    else:
        # /Category/Subject/Chapter
        category_id = get_or_create_folder(category, root_id)
        subject_id = get_or_create_folder(subject, category_id)
        chapter_id = get_or_create_folder(f"Chapter {chapter}", subject_id)
        parent_id = chapter_id

    # Step 2: Upload the file
    file_metadata = {
        'name': filename,
        'parents': [parent_id]
    }

    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype='application/pdf')

    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()

    # Step 3: Make the file public
    drive_service.permissions().create(
        fileId=file['id'],
        body={'type': 'anyone', 'role': 'reader'}
    ).execute()

    return file['id'], file['webViewLink']
def get_or_create_folder(name, parent_id=None):
    query = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder'"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    else:
        query += " and 'root' in parents"

    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    folders = results.get('files', [])

    if folders:
        return folders[0]['id']

    # Folder doesn't exist → Create it
    folder_metadata = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id] if parent_id else []
    }

    folder = drive_service.files().create(body=folder_metadata, fields='id').execute()

    # 🔓 Make the folder public so it shows in browser
    drive_service.permissions().create(
        fileId=folder['id'],
        body={'role': 'reader', 'type': 'anyone'}
    ).execute()

    return folder['id']

