import os
import sys
from dotenv import load_dotenv
from google import genai

# Load environment variables
load_dotenv()

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("Error: GOOGLE_API_KEY not found in .env")
    sys.exit(1)

# Initialize GenAI Client
client = genai.Client(api_key=api_key)

def process_pdf(pdf_path, output_txt_path):
    print(f"Processing {pdf_path}...")
    try:
        import shutil
        import tempfile
        
        # Create a temporary file with .pdf extension and clean name
        temp_dir = tempfile.gettempdir()
        temp_pdf_path = os.path.join(temp_dir, "temp_gemini_upload.pdf")
        shutil.copy2(pdf_path, temp_pdf_path)
        
        try:
            file_obj = client.files.upload(file=temp_pdf_path)
        finally:
            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
        
        print("File uploaded. Generating text extraction...")
        # We use gemini-2.5-flash which is excellent at multimodal document processing
        prompt = "Bu PDF dosyasını dikkatlice incele. İçindeki tüm metinleri ve tabloları Markdown formatında düz metin olarak çıkar. Hiçbir veriyi veya tarihi atlama. Tabloları çok düzgün, okunabilir ve Markdown (veya listeler) halinde sun. Belge Türkçe olduğu için Türkçe karakterlere çok dikkat et."
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[file_obj, prompt]
        )
        
        # Save to output file
        with open(output_txt_path, "w", encoding="utf-8") as f:
            f.write(response.text)
            
        print(f"Success! Saved extracted text to {output_txt_path}")
        
    except Exception as e:
        print(f"Error processing {pdf_path}: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Convert PDF to Markdown Text using Gemini Vision")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    args = parser.parse_args()
    
    # Generate output path by replacing .pdf with .txt
    output_path = os.path.splitext(args.pdf_path)[0] + ".txt"
    process_pdf(args.pdf_path, output_path)
