from flask import Flask, request, abort, render_template, send_file, flash
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
import io
import re
import os
import time
import logging
from typing import Iterable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
from utils import add_start_pages, add_page_numbers_to_pdf
from math import ceil
from pdfrw import PdfReader, PdfWriter, PageMerge
import requests
from google.auth.transport.requests import Request

# -------------------------
# App + logging setup
# -------------------------

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

# -------------------------
# Config
# -------------------------

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]
SERVICE_ACCOUNT_FILE = "service_account.json"
OUTPUT_DIR = "downloads"
SHARED_FOLDER_ID = "0AE0YZ4clOzQ7Uk9PVA"
PDF_DRIVES_ID = "0AMAep1gMANZ_Uk9PVA"

# -------------------------
# Helpers
# -------------------------

def extract_doc_id(url: str) -> str:
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
    if not match:
        raise ValueError("Invalid Google Docs URL")
    return match.group(1)


def get_credentials():
    return service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES,
    )


def drive_client():
    return build("drive", "v3", credentials=get_credentials())


def docs_client():
    return build("docs", "v1", credentials=get_credentials())


def copy_document(drive, doc_id: str, new_name: str) -> str:
    body = {"name": new_name}
    if PDF_DRIVES_ID:
        body["parents"] = [PDF_DRIVES_ID]

    copied = drive.files().copy(
        fileId=doc_id,
        body=body,
        supportsAllDrives=True,
    ).execute()

    logger.info("Created document copy", extra={"doc_id": copied["id"]})
    return copied["id"]


def delete_before_second_page_break(docs, doc_id: str):
    doc = docs.documents().get(documentId=doc_id).execute()
    content = doc.get("body", {}).get("content", [])

    page_break_indices = []

    for element in content:
        if "paragraph" in element:
            for elem in element["paragraph"].get("elements", []):
                if "pageBreak" in elem:
                    page_break_indices.append(elem["startIndex"])

    if len(page_break_indices) < 2:
        logger.info("Less than 2 page breaks found; nothing deleted.")
        return

    requests = [
        {
            "deleteContentRange": {
                "range": {
                    "startIndex": 1,
                    "endIndex": page_break_indices[1],
                }
            }
        }
    ]

    docs.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()
    logger.info("Deleted content before second page break.")

# -------------------------
# Routes
# -------------------------

def generate_pdf(url, title, storyteller_names_str, director_name, crew_id, dedication):
    """Generate a merged PDF from a Google Doc URL and metadata."""
    doc_id = extract_doc_id(url)
    drive = drive_client()
    docs = docs_client()

    meta = drive.files().get(
        fileId=doc_id,
        fields="name,mimeType",
        supportsAllDrives=True
    ).execute()

    if meta["mimeType"] != "application/vnd.google-apps.document":
        abort(400, "File is not a Google Doc")

    file_name = meta["name"]
    logger.info("Processing document", extra={"file_name": file_name})

    temp_doc_id = copy_document(drive, doc_id, f"{file_name} (PDF Copy)")
    delete_before_second_page_break(docs, temp_doc_id)
    time.sleep(2)

    file = drive.files().get(
        fileId=temp_doc_id,
        fields="exportLinks",
        supportsAllDrives=True
    ).execute()

    pdf_url = file["exportLinks"]["application/pdf"]
    logger.info("Generated PDF", extra={"pdf_url": pdf_url})

    credentials = get_credentials()
    token = credentials.token
    if not token:
            credentials.refresh(Request())
            token = credentials.token
    headers = {
        "Authorization": f"Bearer {token}",
    }

    response = requests.get(pdf_url, headers=headers)
    response.raise_for_status()
    # save response content to a file
    with open("temp.pdf", "wb") as f:
        f.write(response.content)

    start_id = add_start_pages(
        SERVICE_ACCOUNT_FILE,
        title,
        storyteller_names_str,
        director_name,
        crew_id,
        dedication,
        "Start Pages",
    )

    def export(doc_id):
        buf = io.BytesIO()
        dl = MediaIoBaseDownload(
            buf,
            drive.files().export_media(
                fileId=doc_id,
                mimeType="application/pdf",
            ),
        )
        done = False
        while not done:
            _, done = dl.next_chunk()
        if buf.getbuffer().nbytes == 0:
            abort(500, "Generated PDF is empty")
        buf.seek(0)
        return buf

    start_buf = export(start_id)
    with open("temp.pdf", "rb") as f:
        pdf_buffer = io.BytesIO(f.read())

    pdf_buffer.seek(0)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"{file_name}.pdf")

    writer = PdfWriter()
    for buf in [start_buf, pdf_buffer, open("end_pages.pdf", "rb")]:
        reader = PdfReader(buf)
        writer.addpages(reader.pages)
    writer.write(output_path)

    add_page_numbers_to_pdf(output_path, output_path)
    logger.info("PDF generated successfully", extra={"path": output_path})

    file_metadata = {
        "name": f"{file_name}.pdf",
        "parents": [PDF_DRIVES_ID],
    }
    media = MediaFileUpload(
        output_path,
        mimetype="application/pdf",
        resumable=True,
    )
    drive.files().create(
        body=file_metadata,
        media_body=media,
        supportsAllDrives=True,
    ).execute()

    return output_path


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("form.html")

    logger.info(
        "Incoming POST request",
        extra={
            "remote_addr": request.remote_addr,
            "user_agent": request.headers.get("User-Agent"),
        },
    )

    data = request.form.to_dict(flat=False)

    for k, v in data.items():
        data[k] = [
            x.replace("\r\n", "\n").replace("\r", "\n") if isinstance(x, str) else x
            for x in v
        ]

    url = data.get("url", [None])[0]
    title = data.get("title", [""])[0]
    storyteller_names = sorted(data.get("storyteller_names", []))
    storyteller_names_str = ", ".join(storyteller_names)
    director_name = data.get("director_name", [""])[0]
    crew_id = data.get("crew_id", [""])[0]
    dedication = data.get("dedication", [""])[0]

    logger.info(
        "Form data parsed",
        extra={
            "url": url,
            "title": title,
            "storyteller_names": storyteller_names_str,
            "director_name": director_name,
            "crew_id": crew_id,
            "dedication_length": len(dedication),
        },
    )

    if not url:
        abort(400, "Missing 'url' field")

    try:
        output_path = generate_pdf(
            url, title, storyteller_names_str, director_name, crew_id, dedication
        )
        flash("Saved successfully", "success")
        return send_file(
            output_path,
            mimetype="application/pdf",
            as_attachment=True,
        )

    except HttpError as e:
        logger.error(
            "Google API error",
            extra={"status": e.resp.status, "error": str(e)},
        )
        abort(e.resp.status, "Google API error")

    except Exception:
        logger.exception("Unhandled error during PDF generation")
        abort(500, "Internal server error")


if __name__ == "__main__":
    app.run(debug=True)
