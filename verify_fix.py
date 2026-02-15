
import os
import logging
from app import add_page_numbers_to_pdf

# Setup logging
logging.basicConfig(level=logging.INFO)

input_pdf = "Automation 2 sample.pdf"
output_pdf = "verified_output.pdf"

if not os.path.exists(input_pdf):
    print(f"Error: {input_pdf} not found.")
    exit(1)

if os.path.exists(output_pdf):
    os.remove(output_pdf)

print(f"Processing {input_pdf}...")
try:
    add_page_numbers_to_pdf(input_pdf, output_pdf)
    
    if os.path.exists(output_pdf):
        size = os.path.getsize(output_pdf)
        print(f"Success! Output generated at {output_pdf}, size: {size} bytes")
    else:
        print("Error: Output file not found after execution.")
except Exception as e:
    print(f"Failed with error: {e}")
    import traceback
    traceback.print_exc()
