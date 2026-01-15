from flask import Flask, request, abort, render_template, send_file
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
import io
import re
import os
import time
import logging
from typing import Iterable
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
from utils import add_start_pages
from werkzeug.middleware.proxy_fix import ProxyFix
# -------------------------
# App + logging setup
# -------------------------

app = Flask(__name__)
app = ProxyFix(app, x_for=1, x_host=1) if os.environ.get("FLASK_ENV") == "production" else app
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


def merge_pdf_buffers(buffers: Iterable[io.BytesIO]) -> io.BytesIO:
    merger = PdfMerger()
    for buf in buffers:
        if not buf:
            continue
        buf.seek(0)
        merger.append(buf)

    out = io.BytesIO()
    merger.write(out)
    merger.close()
    out.seek(0)
    return out


def copy_document(drive, doc_id: str, new_name: str) -> str:
    body = {"name": new_name}
    if SHARED_FOLDER_ID:
        body["parents"] = [SHARED_FOLDER_ID]

    copied = drive.files().copy(
        fileId=doc_id,
        body=body,
        supportsAllDrives=True,
    ).execute()

    logger.info("Created document copy", extra={"doc_id": copied["id"]})
    return copied["id"]


def add_page_numbers_to_pdf(input_pdf_path: str, output_pdf_path: str):
    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()

    pdfmetrics.registerFont(
        TTFont("Lora-Italic", "Lora/static/Lora-Italic.ttf")
    )

    for page_num, page in enumerate(reader.pages, start=1):
        if page_num == 1:
            writer.add_page(page)
            continue

        w = float(page.mediabox.width)
        h = float(page.mediabox.height)

        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=(w, h))
        can.setFont("Lora-Italic", 9)

        text = str(page_num)
        x = (w - can.stringWidth(text, "Lora-Italic", 9)) / 2
        y = 30

        can.drawString(x, y, text)
        can.save()

        packet.seek(0)
        overlay = PdfReader(packet)
        page.merge_page(overlay.pages[0])
        writer.add_page(page)

    with open(output_pdf_path, "wb") as f:
        writer.write(f)

def add_header(docs, doc_id: str, header_text: str):
    # Create header
    response = docs.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"createHeader": {"type": "DEFAULT"}}]},
    ).execute()

    header_id = response["replies"][0]["createHeader"]["headerId"]

    # Insert header text and apply styles
    docs.documents().batchUpdate(
        documentId=doc_id,
        body={
            "requests": [
                {
                    "insertText": {
                        "location": {"segmentId": header_id, "index": 0},
                        "text": header_text,
                    }
                },
                {
                    "updateTextStyle": {
                        "range": {
                            "segmentId": header_id,
                            "startIndex": 0,
                            "endIndex": len(header_text),
                        },
                        "textStyle": {
                            "weightedFontFamily": {"fontFamily": "Lora"},
                            "fontSize": {"magnitude": 9, "unit": "PT"},
                            "italic": True,
                        },
                        "fields": "weightedFontFamily,fontSize,italic",
                    }
                },
                {
                    "updateParagraphStyle": {
                        "range": {
                            "segmentId": header_id,
                            "startIndex": 0,
                            "endIndex": len(header_text),
                        },
                        "paragraphStyle": {"alignment": "CENTER"},
                        "fields": "alignment",
                    }
                },
            ]
        },
    ).execute()

    logger.info("Header added", extra={"doc_id": doc_id})
def delete_before_second_page_break(docs, doc_id: str):
    # Get the document content
    doc = docs.documents().get(documentId=doc_id).execute()
    content = doc.get("body", {}).get("content", [])

    page_break_indices = []
    
    # Walk through elements to find page breaks
    for element in content:
        if "paragraph" in element:
            for elem in element["paragraph"].get("elements", []):
                if "pageBreak" in elem:
                    page_break_indices.append(elem["startIndex"])
    
    if len(page_break_indices) < 2:
        print("Less than 2 page breaks found; nothing deleted.")
        return

    # Delete everything before the second page break
    requests = [
        {
            "deleteContentRange": {
                "range": {
                    "startIndex": 1,
                    "endIndex": page_break_indices[1],  # up to second page break
                }
            }
        }
    ]

    docs.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()
    print("Deleted content before second page break.")

# -------------------------
# Routes
# -------------------------

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

    # sanitize
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
    dedication = data.get("dedication", [""])[0]

    logger.info(
        "Form data parsed",
        extra={
            "url": url,
            "title": title,
            "storyteller_names": storyteller_names_str,
            "director_name": director_name,
            "dedication_length": len(dedication),
        },
    )

    if not url:
        abort(400, "Missing 'url' field")

    try:
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
        # add_header(docs, temp_doc_id, title)
        time.sleep(2)

        export_req = drive.files().export_media(
            fileId=temp_doc_id,
            mimeType="application/pdf",
        )

        pdf_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(pdf_buffer, export_req)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        if pdf_buffer.getbuffer().nbytes == 0:
            abort(500, "Generated PDF is empty")

        start_id = add_start_pages(
            SERVICE_ACCOUNT_FILE,
            title,
            storyteller_names_str,
            director_name,
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
        
        merged = merge_pdf_buffers(
            [export(start_id), pdf_buffer, open("end_pages.pdf", "rb")]
        )

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUT_DIR, f"{file_name}.pdf")

        with open(output_path, "wb") as f:
            f.write(merged.getvalue())

        add_page_numbers_to_pdf(output_path, output_path)

        logger.info("PDF generated successfully", extra={"path": output_path})

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
        logger.error(str(e))
        abort(e.resp.status, "Google API error")

    except Exception:
        logger.exception("Unhandled error during PDF generation")
        abort(500, "Internal server error")


if __name__ == "__main__":
    app.run(debug=True)
