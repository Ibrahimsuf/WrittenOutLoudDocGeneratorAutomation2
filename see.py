from googleapiclient.discovery import build
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
SERVICE_ACCOUNT_FILE = "service_account.json"

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=SCOPES
)

drive = build("drive", "v3", credentials=credentials)

query = "mimeType = 'application/vnd.google-apps.folder' and trashed = false"

folders = []
page_token = None

while True:
    response = drive.files().list(
        q=query,
        spaces="drive",
        corpora="allDrives",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        fields="nextPageToken, files(id, name, parents, driveId)",
        pageToken=page_token,
    ).execute()

    folders.extend(response.get("files", []))
    page_token = response.get("nextPageToken")

    if not page_token:
        break

for f in folders:
    print(f"{f['name']} ({f['id']})")
