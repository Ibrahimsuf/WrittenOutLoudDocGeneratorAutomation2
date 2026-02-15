
import os
import io
from reportlab.pdfgen import canvas
from PyPDF2 import PdfWriter, PdfReader

# Creating a dummy PDF to test
def create_dummy_pdf(filename):
    c = canvas.Canvas(filename)
    c.drawString(100, 750, "Hello World")
    c.showPage()
    c.drawString(100, 750, "Page 2")
    c.save()

# Mocking the function from app.py to test logic 
# (Since importing app.py might trigger other side effects or require google credentials)
import shutil
import tempfile
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO

# Replicating the modified function structure for test
def add_page_numbers_to_pdf(input_pdf_path: str, output_pdf_path: str):
    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()

    # Checking if font exists or mocking it
    # For test, we might skip font registration if file missing, or try/except
    try:
        pdfmetrics.registerFont(
            TTFont("Lora-Italic", "Lora/static/Lora-Italic.ttf")
        )
        font_name = "Lora-Italic"
    except:
        font_name = "Helvetica" # Fallback for test

    for page_num, page in enumerate(reader.pages, start=1):
        if page_num == 1:
            writer.add_page(page)
            continue

        w = float(page.mediabox.width)
        h = float(page.mediabox.height)

        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=(w, h))
        can.setFont(font_name, 9)

        text = str(page_num)
        # simplistic width calc for test
        x = (w - can.stringWidth(text, font_name, 9)) / 2
        y = 30

        can.drawString(x, y, text)
        can.save()

        packet.seek(0)
        overlay = PdfReader(packet)
        page.merge_page(overlay.pages[0])
        writer.add_page(page)

    # The actual change being tested:
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        writer.write(tmp_file)
        temp_path = tmp_file.name

    shutil.move(temp_path, output_pdf_path)

if __name__ == "__main__":
    test_file = "test_output.pdf"
    create_dummy_pdf(test_file)
    print(f"Created {test_file}, size: {os.path.getsize(test_file)}")
    
    # Run user function
    try:
        add_page_numbers_to_pdf(test_file, test_file)
        print(f"Modified {test_file}, size: {os.path.getsize(test_file)}")
        
        # Verify it's a valid PDF
        reader = PdfReader(test_file)
        print(f"Pages: {len(reader.pages)}")
        if len(reader.pages) == 2:
            print("SUCCESS: PDF has 2 pages.")
        else:
            print("FAILURE: Page count mismatch.")
            
    except Exception as e:
        print(f"FAILURE: {e}")
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)
