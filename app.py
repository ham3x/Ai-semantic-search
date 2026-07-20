import os
import io
import uuid
import csv
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import numpy as np
import requests
import chromadb
from pypdf import PdfReader
import docx
from html.parser import HTMLParser
from urllib.parse import unquote, urlparse, parse_qs
import threading
import time

# 1. Initialize Flask App and Enable CORS
app = Flask(__name__, static_folder='frontend/dist', static_url_path='')
CORS(app)  # Allows the frontend to make API calls to this backend safely

# 2. Ollama Embeddings Helper & Pre-verification
def get_ollama_embeddings(inputs, model_name=None):
    if model_name is None:
        model_name = os.environ.get("OLLAMA_MODEL", "nomic-embed-text")
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    url = f"{ollama_url}/api/embed"
    payload = {
        "model": model_name,
        "input": inputs if isinstance(inputs, list) else [inputs]
    }
    try:
        response = requests.post(url, json=payload, timeout=300)
        response.raise_for_status()
        embeddings = response.json()["embeddings"]
        return embeddings if isinstance(inputs, list) else embeddings[0]
    except Exception as e:
        print(f"Error calling Ollama API: {e}")
        raise RuntimeError(f"Failed to generate embeddings via Ollama: {e}")

def ensure_ollama_model():
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    model_name = os.environ.get("OLLAMA_MODEL", "nomic-embed-text")
    # Wait up to 30 seconds for Ollama service to start up
    for _ in range(10):
        try:
            requests.get(ollama_url, timeout=2)
            break
        except Exception:
            time.sleep(3)
    try:
        url = f"{ollama_url}/api/tags"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            models = r.json().get("models", [])
            if any(m.get("name") == model_name or m.get("name").startswith(model_name + ":") for m in models):
                print(f"Ollama model '{model_name}' is already present.")
                return
        
        print(f"Ollama model '{model_name}' not found. Pulling it now (this may take a minute)...")
        pull_url = f"{ollama_url}/api/pull"
        r = requests.post(pull_url, json={"name": model_name}, timeout=300)
        if r.status_code == 200:
            print(f"Successfully pulled Ollama model '{model_name}'.")
        else:
            print(f"Warning: Failed to pull Ollama model. Status code: {r.status_code}")
    except Exception as e:
        print(f"Warning: Could not connect to Ollama to verify/pull model: {e}")

# Run model pre-pull check in the background
threading.Thread(target=ensure_ollama_model, daemon=True).start()

# Dummy embedding function to prevent ChromaDB client from downloading defaults from Hugging Face.
# Since we pre-compute embeddings via Ollama and supply them directly, this is a placeholder.
class DummyEmbeddingFunction(chromadb.EmbeddingFunction):
    def __init__(self):
        pass
    def __call__(self, input):
        return [[] for _ in input]

# 3. Initialize ChromaDB Client based on environment configuration
chroma_mode = os.environ.get("CHROMA_MODE", "persistent").lower()  # Options: 'http', 'persistent', 'ephemeral'
if chroma_mode == "http":
    chroma_host = os.environ.get("CHROMA_HOST", "localhost")
    chroma_port = int(os.environ.get("CHROMA_PORT", 8000))
    print(f"Connecting to ChromaDB Server at http://{chroma_host}:{chroma_port}")
    chroma_client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
elif chroma_mode == "ephemeral":
    print("Using Ephemeral (in-memory) ChromaDB Client")
    chroma_client = chromadb.EphemeralClient()
else:
    persist_dir = os.environ.get("CHROMA_PERSIST_DIR", "./chroma_db")
    print(f"Using Persistent ChromaDB Client at '{persist_dir}'")
    chroma_client = chromadb.PersistentClient(path=persist_dir)

try:
    collection = chroma_client.get_or_create_collection(
        name="document_search",
        metadata={"hnsw:space": "cosine"},
        embedding_function=DummyEmbeddingFunction()
    )
except ValueError:
    # If there is a schema conflict (e.g. database has old collection with default embedding function),
    # delete it and recreate it with the dummy function.
    try:
        chroma_client.delete_collection("document_search")
    except Exception:
        pass
    collection = chroma_client.get_or_create_collection(
        name="document_search",
        metadata={"hnsw:space": "cosine"},
        embedding_function=DummyEmbeddingFunction()
    )

# Helper functions to extract text from different file types
def parse_pdf(file_bytes):
    pdf_file = io.BytesIO(file_bytes)
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text

def parse_docx(file_bytes):
    doc = docx.Document(io.BytesIO(file_bytes))
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    for table in doc.tables:
        for row in table.rows:
            row_text = [cell.text for cell in row.cells]
            full_text.append(" | ".join(row_text))
    return "\n".join(full_text)

def parse_csv(file_bytes):
    text_content = file_bytes.decode('utf-8', errors='ignore')
    reader = csv.reader(io.StringIO(text_content))
    rows = []
    for row in reader:
        rows.append(", ".join(row))
    return "\n".join(rows)

def parse_txt(file_bytes):
    return file_bytes.decode('utf-8', errors='ignore')


# 4. HTML Parser to extract DuckDuckGo Search Results
# We extract results directly from the static HTML version of DuckDuckGo.
# This bypasses JavaScript execution and TLS 1.3 protocol negotiation errors on macOS.
class DuckDuckGoParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self.current_result = None
        self.in_title = False
        self.in_snippet = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = attrs_dict.get('class', '')

        # Start of a new result item (the title link)
        if tag == 'a' and 'result__a' in classes:
            # Save the current result before starting the next one
            if self.current_result:
                self.results.append(self.current_result)
            
            href = attrs_dict.get('href', '')
            # Decode the DuckDuckGo redirect URL to get the clean original link
            if 'uddg=' in href:
                parsed = urlparse(href)
                qs = parse_qs(parsed.query)
                if 'uddg' in qs:
                    href = qs['uddg'][0]
            
            self.current_result = {
                "title": "",
                "url": href,
                "snippet": ""
            }
            self.in_title = True

        # Snippet block
        elif tag == 'a' and 'result__snippet' in classes:
            self.in_snippet = True

    def handle_endtag(self, tag):
        if tag == 'a':
            self.in_title = False
            self.in_snippet = False

    def handle_data(self, data):
        if self.in_title and self.current_result:
            self.current_result["title"] += data
        elif self.in_snippet and self.current_result:
            self.current_result["snippet"] += data

    def close(self):
        super().close()
        # Append the final result if one is left over
        if self.current_result:
            self.results.append(self.current_result)


def search_ddg_html(query):
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    data = {"q": query}
    try:
        response = requests.post(url, data=data, headers=headers, timeout=10)
        if response.status_code != 200:
            return []
        
        parser = DuckDuckGoParser()
        parser.feed(response.text)
        parser.close()
        return parser.results
    except Exception as e:
        print(f"Error fetching from DuckDuckGo: {e}")
        return []


# 5. Route to serve the HTML Frontend
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


# 6. Route to handle the API Search Request
@app.route('/api/search', methods=['GET'])
def search_api():
    query = request.args.get('q', '').strip()
    mode = request.args.get('mode', 'web').strip()  # Mode can be 'web' or 'local'
    
    if not query:
        return jsonify([])

    # --- MODE: WEB (Real-time AI search engine) ---
    if mode == 'web':
        # 1. Fetch real-time web results from DuckDuckGo
        web_results = search_ddg_html(query)
        
        # If web search fails, fallback to local database
        if not web_results:
            print("Web search returned no results. Falling back to local database.")
            mode = 'local'
        else:
            # 2. Extract snippets to perform semantic ranking
            snippets = [r["snippet"] for r in web_results]
            
            # 3. Generate embeddings for query and snippets using Ollama
            try:
                web_embeddings = np.array(get_ollama_embeddings(snippets))
                query_embedding = np.array(get_ollama_embeddings(query))
                
                # 4. Compute cosine similarity scores
                # Normalize embeddings to ensure dot product is exactly cosine similarity
                web_embeddings_norm = web_embeddings / np.linalg.norm(web_embeddings, axis=1, keepdims=True)
                query_embedding_norm = query_embedding / np.linalg.norm(query_embedding)
                scores = np.dot(web_embeddings_norm, query_embedding_norm)
            except Exception as e:
                print(f"Failed to calculate similarity using Ollama: {e}")
                scores = [0.5] * len(web_results)
            
            # 5. Build results list sorted by similarity score
            results = []
            for idx, score in enumerate(scores):
                results.append({
                    "title": web_results[idx]["title"],
                    "text": web_results[idx]["snippet"],
                    "source": web_results[idx]["url"],
                    "score": float(score)
                })
            
            results = sorted(results, key=lambda x: x["score"], reverse=True)
            return jsonify(results)

    # --- MODE: LOCAL (Semantic search on uploaded files in ChromaDB) ---
    if mode == 'local':
        try:
            count = collection.count()
            if count == 0:
                return jsonify({"error": "No files have been uploaded to the local database yet. Please upload files first."}), 400

            query_embedding = get_ollama_embeddings(query)
            # Fetch up to 10 matching chunks
            query_results = collection.query(
                query_embeddings=[query_embedding],
                n_results=min(10, count)
            )

            results = []
            if query_results and 'documents' in query_results and len(query_results['documents']) > 0:
                ids = query_results['ids'][0]
                documents = query_results['documents'][0]
                metadatas = query_results['metadatas'][0]
                distances = query_results['distances'][0]

                for idx, doc in enumerate(documents):
                    # Cosine distance = 1 - cosine_similarity. So cosine_similarity = 1 - distance.
                    dist = float(distances[idx])
                    score = max(0.0, min(1.0, 1.0 - dist))
                    source = metadatas[idx].get('source', 'Uploaded File')

                    results.append({
                        "title": f"Match {idx+1} from {source}",
                        "text": doc,
                        "source": source,
                        "score": score
                    })

                results = sorted(results, key=lambda x: x["score"], reverse=True)
            return jsonify(results)
        except Exception as e:
            return jsonify({"error": f"Failed to search local database: {str(e)}"}), 500

    return jsonify({"error": f"Invalid search mode: {mode}"}), 400


# 7. Route to upload PDF/TXT/DOCX/CSV documents
@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in request"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    filename = file.filename
    file_bytes = file.read()
    text = ""
    
    # 1. Parse text depending on file format extension
    ext = os.path.splitext(filename)[1].lower()
    
    try:
        if ext == '.pdf':
            text = parse_pdf(file_bytes)
        elif ext == '.docx':
            text = parse_docx(file_bytes)
        elif ext == '.csv':
            text = parse_csv(file_bytes)
        elif ext in ['.txt', '.md', '.json', '.xml']:
            text = parse_txt(file_bytes)
        else:
            return jsonify({"error": f"Unsupported format '{ext}'. Please upload .pdf, .docx, .csv, or .txt"}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to parse '{filename}': {str(e)}"}), 500
        
    if not text.strip():
        return jsonify({"error": f"No readable text found in '{filename}'."}), 400
        
    # 2. Chunk text: Split by paragraphs, filter out very short chunks
    paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 30]
    
    # Fallback splitting strategies if double newlines don't yield multiple chunks
    if len(paragraphs) <= 1:
        # Split by single newline if they are long lines
        paragraphs = [p.strip() for p in text.split('\n') if len(p.strip()) > 50]
        
    if not paragraphs:
        # Split by fixed size chunking
        chunk_size = 500
        paragraphs = [text[i:i+chunk_size].strip() for i in range(0, len(text), chunk_size)]
        paragraphs = [p for p in paragraphs if len(p) > 10]
        
    if not paragraphs:
        return jsonify({"error": f"No readable text chunks could be extracted from '{filename}'."}), 400
        
    try:
        # Prevent duplicates: delete any existing chunks from the same file name first
        try:
            collection.delete(where={"source": filename})
        except Exception:
            pass
        
        # 3. Generate embeddings using Ollama
        embeddings = get_ollama_embeddings(paragraphs)
        
        # 4. Insert into the ChromaDB collection
        ids = [f"{filename}_chunk_{uuid.uuid4().hex}" for _ in paragraphs]
        metadatas = [{"source": filename} for _ in paragraphs]
        
        collection.add(
            embeddings=embeddings,
            documents=paragraphs,
            ids=ids,
            metadatas=metadatas
        )
        return jsonify({
            "message": f"Successfully parsed and loaded {len(paragraphs)} sections from '{filename}' into memory.",
            "filename": filename,
            "chunks_count": len(paragraphs)
        })
    except Exception as e:
        return jsonify({"error": f"Failed to store document: {str(e)}"}), 500


# 8. Route to delete a specific file
@app.route('/api/upload/delete', methods=['POST'])
def delete_file():
    data = request.get_json() or {}
    filename = data.get('filename')
    if not filename:
        return jsonify({"error": "No filename provided"}), 400
    try:
        collection.delete(where={"source": filename})
        return jsonify({"message": f"Successfully deleted '{filename}' from the database."})
    except Exception as e:
        return jsonify({"error": f"Failed to delete file '{filename}': {str(e)}"}), 500


# 9. Route to clear the entire database
@app.route('/api/upload/clear', methods=['POST'])
def clear_database():
    global collection
    try:
        chroma_client.delete_collection("document_search")
    except Exception:
        pass
    collection = chroma_client.get_or_create_collection(
        name="document_search",
        metadata={"hnsw:space": "cosine"},
        embedding_function=DummyEmbeddingFunction()
    )
    return jsonify({"message": "Successfully cleared all documents from the database."})


# 10. Route to fetch current upload status (list of all uploaded files and total chunks)
@app.route('/api/upload/status', methods=['GET'])
def upload_status():
    try:
        count = collection.count()
        if count > 0:
            # Fetch all metadatas to extract unique sources
            data = collection.get(include=["metadatas"])
            filenames = sorted(list(set(m.get('source', 'Unknown File') for m in data.get('metadatas', []) if m)))
            return jsonify({
                "uploaded": True,
                "filenames": filenames,
                "chunks_count": count
            })
        else:
            return jsonify({
                "uploaded": False,
                "filenames": [],
                "chunks_count": 0
            })
    except Exception as e:
        return jsonify({
            "error": str(e),
            "uploaded": False,
            "filenames": [],
            "chunks_count": 0
        }), 500


if __name__ == '__main__':
    print("Starting Semantic Search Python Server at http://0.0.0.0:5002")
    app.run(host='0.0.0.0', port=5002, debug=True)