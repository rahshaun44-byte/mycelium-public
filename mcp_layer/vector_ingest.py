import os
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Absolute Paths for Zero-Trust Routing
BASE_DIR = os.path.expanduser("~/mycelium")
KB_DIRS = [
    os.path.join(BASE_DIR, "knowledge_vault"),
    os.path.join(BASE_DIR, "sentinel/knowledge_base")
]
DB_DIR = os.path.join(BASE_DIR, "sentinel/chroma_db")
COLLECTION_NAME = "quantum_flex_kb"

def ingest_knowledge():
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    documents = []
    loaded_count = 0

    for kb_dir in KB_DIRS:
        if not os.path.exists(kb_dir):
            continue
        for filename in os.listdir(kb_dir):
            if filename.endswith(".txt") or filename.endswith(".md"):
                file_path = os.path.join(kb_dir, filename)
                print(f"[+] Loading: {file_path}")
                try:
                    loader = TextLoader(file_path, encoding="utf-8")
                    documents.extend(loader.load())
                    loaded_count += 1
                except Exception as e:
                    print(f"[-] Error loading {filename}: {e}")

    if not documents:
        print("[-] Error: No documents loaded from knowledge vaults.")
        return

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    texts = text_splitter.split_documents(documents)

    print(f"[+] Indexing {len(texts)} chunks into collection: {COLLECTION_NAME}...")
    Chroma.from_documents(
        texts, 
        embeddings, 
        collection_name=COLLECTION_NAME, 
        persist_directory=DB_DIR
    )
    print(f"[+] Success. Database persisted to {DB_DIR}")

if __name__ == "__main__":
    ingest_knowledge()
