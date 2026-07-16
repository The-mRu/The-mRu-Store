import os
import asyncio
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader
import docx

# 1. Setup
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "amazon_clone_db") 

mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client[MONGO_DB_NAME]

print("Loading AI Model...")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

def extract_text_from_pdf(file_path):
    """Extracts text from a PDF file."""
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        if page.extract_text():
            text += page.extract_text() + "\n"
    return text

def extract_text_from_docx(file_path):
    """Extracts text from a Word document."""
    doc = docx.Document(file_path)
    text = ""
    for para in doc.paragraphs:
        if para.text.strip():
            text += para.text + "\n"
    return text

def extract_text_from_txt(file_path):
    """Extracts text from a standard TXT file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()

async def process_document(file_path, source_name):
    print(f"Reading {source_name}...")
    
    # Extract text based on file extension
    file_ext = file_path.lower()
    if file_ext.endswith('.pdf'):
        raw_text = extract_text_from_pdf(file_path)
    elif file_ext.endswith('.docx'):
        raw_text = extract_text_from_docx(file_path)
    elif file_ext.endswith('.txt'):
        raw_text = extract_text_from_txt(file_path)
    else:
        return

    # Chop the text into small paragraphs (chunks)
    paragraphs = raw_text.split('\n')
    valid_chunks = [p.strip() for p in paragraphs if len(p.strip()) > 50] # Ignore tiny fragments

    print(f"  -> Found {len(valid_chunks)} readable paragraphs. Vectorizing...")
    
    # Clear old data from this SPECIFIC file so we don't get duplicates on updates
    await db.StoreKnowledge.delete_many({"source": source_name})

    # Translate and save each paragraph
    count = 0
    for chunk in valid_chunks:
        vector = embedding_model.encode(chunk).tolist()
        doc_record = {
            "source": source_name,
            "content": chunk,
            "embedding": vector
        }
        await db.StoreKnowledge.insert_one(doc_record)
        count += 1
        
    print(f"  -> Saved {count} vectors to database for {source_name}.\n")

async def main():
    docs_dir = os.path.join("docs", "static")
    
    if not os.path.exists(docs_dir):
        print(f"Directory '{docs_dir}' does not exist. Please create it and add files.")
        return

    print(f"Scanning '{docs_dir}' for documents...\n")
    
    # Dynamically loop through every file in the folder
    files_processed = 0
    for filename in os.listdir(docs_dir):
        file_path = os.path.join(docs_dir, filename)
        
        # Make sure it's a file (not a sub-folder) and has a supported extension
        if os.path.isfile(file_path):
            if filename.lower().endswith(('.pdf', '.docx', '.txt')):
                await process_document(file_path, source_name=filename)
                files_processed += 1
            else:
                print(f"Skipping {filename} (Unsupported format)")
                
    if files_processed == 0:
        print("No supported files (.pdf, .docx, .txt) found in the directory.")
    else:
        print("✅ All Documents Ingested Successfully!")

if __name__ == "__main__":
    asyncio.run(main())
    
    
    
### python scripts/ingest_docs.py