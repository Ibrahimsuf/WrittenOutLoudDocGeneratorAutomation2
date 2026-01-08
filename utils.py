from google.oauth2 import service_account
from googleapiclient.discovery import build
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO

START_PAGES_ID = "1niKJyWqADraNMjGoAiyiUgqwOnO-2o0_n219_zr8Tug"
END_PAGES_ID="1PGth0S9u1dCF-fb-qQkscfWDYNl1GKZaAK_J9Pr3CSQ"
SHARED_FOLDER_ID = "0AE0YZ4clOzQ7Uk9PVA"
SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

def add_end_pages(credentials_path: str, title: str, new_doc_name: str) -> str:
    creds = service_account.Credentials.from_service_account_file(
        credentials_path,
        scopes=SCOPES,
    )

    docs_service = build("docs", "v1", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    # 1. Copy the document
    copied_file = drive_service.files().copy(
        fileId=END_PAGES_ID,
        body={"name": new_doc_name, "parents": [SHARED_FOLDER_ID]},
        supportsAllDrives=True
    ).execute()

    new_doc_id = copied_file["id"]

    # 2. Replace {{title}} everywhere
    requests = [
        {
            "replaceAllText": {
                "containsText": {
                    "text": "{{title}}",
                    "matchCase": True,
                },
                "replaceText": title,
            }
        },
    ]

    # print(requests)

    docs_service.documents().batchUpdate(
        documentId=new_doc_id,
        body={"requests": requests},
    ).execute()

    # share with anyone with link
    drive_service.permissions().create(
    fileId=new_doc_id,
    body={
        "type": "anyone",
        "role": "reader",  # or "writer"
    },
    fields="id",
    supportsAllDrives=True
).execute()

    return new_doc_id


def add_start_pages(
    credentials_path: str,
    title: str,
    storyteller_names: str,
    director_name: str,
    dedication: str,
    new_doc_name: str,
) -> str:
    creds = service_account.Credentials.from_service_account_file(
        credentials_path,
        scopes=SCOPES,
    )

    docs_service = build("docs", "v1", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    # 1. Copy the document
    copied_file = drive_service.files().copy(
        fileId=START_PAGES_ID,
        body={"name": new_doc_name, "parents": [SHARED_FOLDER_ID]},
        supportsAllDrives=True
    ).execute()

    new_doc_id = copied_file["id"]

    # 2. Replace {{title}} everywhere
    requests = [
        {
            "replaceAllText": {
                "containsText": {
                    "text": "{{title}}",
                    "matchCase": True,
                },
                "replaceText": title,
            }
        },
        {
            "replaceAllText": {
                "containsText": {
                    "text": "{{storyteller_names}}",
                    "matchCase": True,
                },
                "replaceText": storyteller_names,
            }
        },
        {
            "replaceAllText": {
                "containsText": {
                    "text": "{{director_name}}",
                    "matchCase": True,
                },
                "replaceText": director_name,
            }
        },
        {
            "replaceAllText": {
                "containsText": {
                    "text": "{{dedication}}",
                    "matchCase": True,
                },
                "replaceText": dedication,
            }
        }
    ]
    # print("Requests:", requests)

    docs_service.documents().batchUpdate(
        documentId=new_doc_id,
        body={"requests": requests},
    ).execute()

    # share with anyone with link
    drive_service.permissions().create(
    fileId=new_doc_id,
    body={
        "type": "anyone",
        "role": "reader",  # or "writer"
    },
    fields="id",
    supportsAllDrives=True
).execute()

    return new_doc_id
def add_page_numbers_to_pdf(input_pdf_path: str, output_pdf_path: str, footer_text: str = ""):
    """Add page numbers to existing PDF"""
    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()
    
    pdfmetrics.registerFont(TTFont('Lora-Italic', 'Lora/static/Lora-Italic.ttf'))
    
    for page_num, page in enumerate(reader.pages):
        # Get page dimensions
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)
        
        # Create footer overlay
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=(page_width, page_height))
        can.setFont("Lora-Italic", 9)
        # Create footer text with page number
        text = str(page_num)
        
        # Center the text
        text_width = can.stringWidth(text, "Lora-Italic", 9)
        x = (page_width - text_width) / 2
        y = 30  # 30 points from bottom
        
        can.drawString(x, y, text,)
        can.save()
        
        # Merge footer with original page
        packet.seek(0)
        footer_pdf = PdfReader(packet)
        page.merge_page(footer_pdf.pages[0])
        writer.add_page(page)
    
    # Write output
    with open(output_pdf_path, 'wb') as output_file:
        writer.write(output_file)
    
    print(f"PDF with page numbers saved to {output_pdf_path}")