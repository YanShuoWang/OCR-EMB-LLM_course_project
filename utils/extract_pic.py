[file name]: extract_pic.py
[file content begin]
import fitz  # PyMuPDF library import name is fitz
import os

def pdf_to_images(pdf_path, output_folder, dpi=300):
    """
    Convert each page of a PDF file into an image.

    :param pdf_path: Input PDF file path
    :param output_folder: Output folder path for images
    :param dpi: DPI (Dots Per Inch) for generated images, higher value means clearer images but larger file size
    """
    # 1. Ensure output folder exists, create if not
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Created folder: {output_folder}")

    # 2. Open PDF file
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error: Unable to open PDF file '{pdf_path}'. Error: {e}")
        return

    # Get total number of pages in PDF for leading zero formatting
    num_pages = len(doc)
    # Calculate number of digits needed (e.g., 99 pages need 2 digits, 100 pages need 3 digits)
    page_num_width = len(str(num_pages)) 
    
    print(f"Starting PDF conversion: '{pdf_path}', total {num_pages} pages...")

    # 3. Iterate through each page and save as image
    for page_num in range(num_pages):
        page = doc.load_page(page_num)  # Load page
        
        # Set scaling matrix for higher DPI
        # matrix = fitz.Matrix(zoom_x, zoom_y)
        # Default DPI is 72, so dpi/72 is the scaling factor
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)

        # Get page pixmap
        pix = page.get_pixmap(matrix=matrix)
        
        # 4. Build output image filename
        # Use f-string with leading zero formatting to ensure files are numerically ordered
        # Example: page_001.png, page_002.png, ...
        image_filename = f"page_{page_num + 1:0{page_num_width}d}.png"
        output_path = os.path.join(output_folder, image_filename)
        
        # 5. Save image
        pix.save(output_path)
        print(f"Saved: {output_path}")

    # 6. Close PDF document
    doc.close()
    print("\nAll pages successfully converted to images!")

# --- Usage example ---
if __name__ == "__main__":
    # PDF file path to convert (please modify to your file path)
    # On Windows, path might be "C:\\Users\\YourUser\\Documents\\example.pdf"
    # On macOS or Linux, path might be "/home/user/docs/example.pdf"
    my_pdf_file = "dataset/raw/Knowledge.pdf" 
    
    # Target folder for saving images (please modify to your desired folder name)
    my_output_folder = "Pictures"
    
    # Call function to start conversion
    pdf_to_images(my_pdf_file, my_output_folder)
[file content end]