import os
import glob
import shutil
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

load_dotenv()

# Proje kök dizinini bul (bu dosya src/ içinde olduğu için bir üst dizin)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DATA_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
CHROMA_DIR = os.path.join(PROJECT_ROOT, "data", "chroma")

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

def load_documents():
    documents = []
    
    # Load PDFs
    pdf_files = glob.glob(os.path.join(RAW_DATA_DIR, "*.pdf"))
    for pdf_file in pdf_files:
        print(f"Loading {pdf_file}...")
        try:
            loader = PyPDFLoader(pdf_file)
            documents.extend(loader.load())
        except Exception as e:
            print(f"  Warning: Could not load {pdf_file}: {e}")
        
    # Load TXTs
    txt_files = glob.glob(os.path.join(RAW_DATA_DIR, "*.txt"))
    for txt_file in txt_files:
        print(f"Loading {txt_file}...")
        try:
            loader = TextLoader(txt_file, encoding='utf-8')
            documents.extend(loader.load())
        except Exception as e:
            print(f"  Warning: Could not load {txt_file}: {e}")
        
    # Load DOCXs
    docx_files = glob.glob(os.path.join(RAW_DATA_DIR, "*.docx"))
    for docx_file in docx_files:
        print(f"Loading {docx_file}...")
        try:
            loader = Docx2txtLoader(docx_file)
            documents.extend(loader.load())
        except Exception as e:
            print(f"  Warning: Could not load {docx_file}: {e}")
        
    return documents

def main():
    print("Starting ingestion process...")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Raw data dir: {RAW_DATA_DIR}")
    print(f"Chroma dir: {CHROMA_DIR}")
    
    documents = load_documents()
    
    if not documents:
        print(f"No documents found in {RAW_DATA_DIR}. Please add some PDFs or TXTs.")
        return

    print(f"Loaded {len(documents)} document pages/sections.")
    
    # Split texts
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        length_function=len
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Split into {len(chunks)} chunks.")
    
    # Eski veritabanını tamamen sil (duplikasyonu önlemek için)
    if os.path.exists(CHROMA_DIR):
        print(f"Removing old ChromaDB at {CHROMA_DIR}...")
        shutil.rmtree(CHROMA_DIR)
    
    # Embed and store
    print(f"Initializing embeddings with model: {EMBEDDING_MODEL}")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    
    # Temiz bir veritabanı oluştur
    db = Chroma.from_documents(
        chunks, 
        embeddings, 
        persist_directory=CHROMA_DIR
    )
    
    print(f"Successfully ingested {len(chunks)} chunks into ChromaDB at {CHROMA_DIR}.")

if __name__ == "__main__":
    main()
