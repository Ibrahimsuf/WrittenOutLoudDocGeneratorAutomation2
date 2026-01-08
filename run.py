from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO

def add_page_numbers_to_pdf(input_pdf_path: str, output_pdf_path: str, footer_text: str = ""):
    """Add page numbers to existing PDF"""
    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()
    
    pdfmetrics.registerFont(TTFont('Lora-Italic', 'Lora/static/Lora-Italic.ttf'))
    
    for page_num, page in enumerate(reader.pages, 1):
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