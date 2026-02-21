from google.oauth2 import service_account
from googleapiclient.discovery import build
from pdfrw import PdfReader, PdfWriter, PageMerge
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
from datetime import datetime

START_PAGES_ID = "1niKJyWqADraNMjGoAiyiUgqwOnO-2o0_n219_zr8Tug"
SHARED_FOLDER_ID = "0AE0YZ4clOzQ7Uk9PVA"
SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]


def add_start_pages(
    credentials_path: str,
    title: str,
    storyteller_names: str,
    director_name: str,
    crew_id: str,
    dedication: str,
    new_doc_name: str,
) -> str:
    creds = service_account.Credentials.from_service_account_file(
        credentials_path,
        scopes=SCOPES,
    )

    docs_service = build("docs", "v1", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    # Copy the document
    copied_file = drive_service.files().copy(
        fileId=START_PAGES_ID,
        body={"name": new_doc_name, "parents": [SHARED_FOLDER_ID]},
        supportsAllDrives=True,
    ).execute()

    new_doc_id = copied_file["id"]

    requests = [
        {
            "replaceAllText": {
                "containsText": {"text": "{{title}}", "matchCase": True},
                "replaceText": title,
            }
        },
        {
            "replaceAllText": {
                "containsText": {"text": "{{storyteller_names}}", "matchCase": True},
                "replaceText": storyteller_names,
            }
        },
        {
            "replaceAllText": {
                "containsText": {"text": "{{director_name}}", "matchCase": True},
                "replaceText": director_name,
            }
        },
        {
            "replaceAllText": {
                "containsText": {"text": "{{crew_id}}", "matchCase": True},
                "replaceText": crew_id,
            }
        },
        {
            "replaceAllText": {
                "containsText": {"text": "{{dedication}}", "matchCase": True},
                "replaceText": dedication,
            }
        },
        {
            "replaceAllText": {
                "containsText": {"text": "{{year}}", "matchCase": True},
                "replaceText": str(datetime.now().year),
            }
        },
    ]

    docs_service.documents().batchUpdate(
        documentId=new_doc_id,
        body={"requests": requests},
    ).execute()

    drive_service.permissions().create(
        fileId=new_doc_id,
        body={"type": "anyone", "role": "reader"},
        fields="id",
        supportsAllDrives=True,
    ).execute()

    return new_doc_id


def add_page_numbers_to_pdf(input_pdf_path: str, output_pdf_path: str):
    """Add centered page numbers to an existing PDF using Lora Italic font."""
    pdfmetrics.registerFont(TTFont("Lora-Italic", "Lora/static/Lora-Italic.ttf"))

    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()

    for page_num, page in enumerate(reader.pages):
        mbox = [float(x) for x in page.MediaBox]
        width = mbox[2] - mbox[0]
        height = mbox[3] - mbox[1]

        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=(width, height))
        can.setFont("Lora-Italic", 9)

        text = str(page_num + 1)
        text_width = can.stringWidth(text, "Lora-Italic", 9)
        x = (width - text_width) / 2
        y = 30

        can.drawString(x, y, text)
        can.save()

        packet.seek(0)
        footer_page = PdfReader(packet).pages[0]
        PageMerge(page).add(footer_page).render()
        writer.addpage(page)

    writer.write(output_pdf_path)
