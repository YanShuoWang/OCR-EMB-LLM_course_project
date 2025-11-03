import base64
import os
import time
from volcenginesdkarkruntime import Ark

# --- Initialize client ---
try:
    client = Ark(
        api_key=os.getenv('ARK_API_KEY'),
    )
except Exception as e:
    print(f"Initialization failed, please check if API Key is correctly set as environment variable 'ARK_API_KEY'. Error: {e}")
    exit()

# --- Global variables and path definitions ---
PICTURES_DIR = 'Pictures'
OUTPUT_FILE = 'math_ocr_results.txt'
PROCESSED_RECORD_FILE = 'processed_images.txt'

# --- Core functions ---

def encode_image(image_path):
    """Convert image file at specified path to Base64 encoding"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def get_math_ocr_result(image_path):
    """
    Call Doubao API to get OCR results for math formula images (Markdown format).
    Returns: (ocr_result, error_message)
    """
    if not os.path.exists(image_path):
        error_msg = f"File does not exist"
        print(f"Warning: {error_msg} {image_path}")
        return None, error_msg
        
    try:
        base64_image = encode_image(image_path)
        
        response = client.chat.completions.create(
            model="doubao-seed-1-6-vision-250815",
            messages=[
                {
                    "role": "user",
                    "content": [
                        { "type": "image_url", "image_url": { "url": f"data:image/png;base64,{base64_image}" } },
                        { 
                            "type": "text", 
                            "text": """请对这张考研数学图片进行OCR识别，提取所有数学公式和知识点。
要求：
1. 只保留数学公式、定理、定义、例题等核心内容，去除所有无关文字和装饰性元素
2. 使用规范的Markdown格式输出
3. 数学公式请使用LaTeX语法表示，例如：$E = mc^2$
4. 保持原图片中的逻辑结构和层次关系
5. 如果是例题，请完整提取题目和解题过程"""
                        },
                    ],
                }
            ],
            thinking={ "type": "disabled" },
        )
        
        ocr_result = response.choices[0].message.content
        
        print(f"Successfully processed: {image_path}")
        return ocr_result, None

    except Exception as e:
        error_msg = f"API call or processing error: {e}"
        print(f"Error: Failed to process image {image_path}. Reason: {e}")
        return None, error_msg

def load_processed_images():
    """Load record of processed images"""
    processed = set()
    if os.path.exists(PROCESSED_RECORD_FILE):
        try:
            with open(PROCESSED_RECORD_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    processed.add(line.strip())
        except Exception as e:
            print(f"Failed to read processing record file: {e}")
    return processed

def save_processed_image(image_name):
    """Save record of processed images"""
    try:
        with open(PROCESSED_RECORD_FILE, 'a', encoding='utf-8') as f:
            f.write(image_name + '\n')
    except Exception as e:
        print(f"Failed to save processing record: {e}")

def save_ocr_result(result_text, page_num):
    """Save OCR results to txt file"""
    try:
        with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
            f.write("\n\n")
            f.write(result_text)
            f.write("\n\n")
    except Exception as e:
        print(f"Failed to save OCR results: {e}")

# --- Main program entry ---
if __name__ == "__main__":
    # Ensure folder exists
    if not os.path.exists(PICTURES_DIR):
        print(f"Error: Please ensure '{PICTURES_DIR}' folder exists in current directory.")
        exit()

    # Initialize output file
    if os.path.exists(OUTPUT_FILE):
        # Backup existing file
        backup_name = f"backup_{int(time.time())}_{OUTPUT_FILE}"
        os.rename(OUTPUT_FILE, backup_name)
        print(f"Backed up existing result file as: {backup_name}")
    
    # Create new output file and write title
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("考研数学公式")
        f.write("\n\n")

    # Load processed images record
    processed_images = load_processed_images()
    failed_images = []
    
    print(f"--- Starting to process directory: {PICTURES_DIR} (Total 40 images) ---")
    
    # Process all images from 001 to 040
    for i in range(1, 41):
        image_name = f"page_{i:02d}.png"
        image_path = os.path.join(PICTURES_DIR, image_name)
        
        # Check if already processed
        if image_name in processed_images:
            print(f"Already processed, skipping: {image_name}")
            continue

        # Check if file exists
        if not os.path.exists(image_path):
            print(f"File does not exist, skipping: {image_name}")
            continue
            
        print(f"Processing: {image_name}")
        
        ocr_result, error = get_math_ocr_result(image_path)
        
        if error:
            failed_images.append({'path': image_path, 'reason': error})
            print(f"Processing failed: {image_name} - {error}")
        else:
            # Save OCR result
            save_ocr_result(ocr_result, i)
            # Record as processed
            save_processed_image(image_name)
            print(f"Successfully processed: {image_name}")
        
        # Add delay to avoid frequent API requests
        time.sleep(1)

    # Final summary
    print(f"\n--- Processing completed ---")
    print(f"OCR results saved to: {OUTPUT_FILE}")
    print(f"Processing record saved to: {PROCESSED_RECORD_FILE}")

    # Error summary
    if not failed_images:
        print("\n🎉 All processing completed without any errors.")
    else:
        print(f"\n--- Error summary: {len(failed_images)} images failed to process ---")
        for failure in failed_images:
            print(f"  - File: {failure['path']}")
            print(f"    Reason: {failure['reason']}")
