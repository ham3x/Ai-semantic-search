import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from sentence_transformers import SentenceTransformer
import numpy as np
import requests
import io
import chromadb
from pypdf import pdfreder
from html.parser import HTMLParser
from urllib.parse import unquote, urlparse, parse_qs
sql= os.environ("MYSQL")
# 1. Initialize Flask App and Enable CORS
app = Flask(__name__, static_folder='frontend/dist', static_url_path='')
CORS(app)  # Allows the frontend to make API calls to this backend safely

# 2. Load the Lightweight Semantic Search Model
# This downloads/loads the ~80MB all-MiniLM-L6-v2 model and runs it locally on CPU.
model = SentenceTransformer('all-MiniLM-L6-v2')

# 3. Define the Local Corpus of Knowledge
# Each entry contains a title, the actual text, and the source URL/citation.
local_documents = [
    {
        "title": "Theory of Relativity",
        "text": "Albert Einstein developed the theory of relativity, which consists of special relativity and general relativity. It revolutionized physics by introducing the concept that space and time are interwoven into a single continuum known as spacetime.",
        "source": "https://en.wikipedia.org/wiki/Theory_of_relativity"
    },
    {
        "title": "Photosynthesis Process",
        "text": "Photosynthesis is the chemical process used by plants, algae, and certain bacteria to harness energy from sunlight and turn it into chemical energy, specifically sugars, while releasing oxygen as a byproduct.",
        "source": "https://en.wikipedia.org/wiki/Photosynthesis"
    },
    {
        "title": "The ENIAC Computer",
        "text": "Built in 1945, the Electronic Numerical Integrator and Computer (ENIAC) was the first programmable, electronic, general-purpose digital computer. It was Turing-complete and used to calculate artillery firing tables.",
        "source": "https://en.wikipedia.org/wiki/ENIAC"
    },
    {
        "title": "Healthy Diet Guidelines",
        "text": "A healthy diet is rich in nutrient-dense foods, including fruits, vegetables, whole grains, lean proteins, and healthy fats. It avoids processed foods, refined sugars, and excessive sodium to reduce chronic disease risks.",
        "source": "https://www.health.harvard.edu/"
    },
    {
        "title": "Quantum Computing Basics",
        "text": "Quantum computers use qubits instead of classical bits. Qubits leverage quantum mechanics concepts like superposition and entanglement to perform complex computations much faster than traditional computers.",
        "source": "https://en.wikipedia.org/wiki/Quantum_computing"
    }
]

# 4. Precompute Local Document Embeddings
local_texts = [doc["text"] for doc in local_documents]
local_embeddings = model.encode(local_texts, normalize_embeddings=True)


# 5. HTML Parser to extract DuckDuckGo Search Results
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
    params = {"q": query}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code != 200:
            return []
        
        parser = DuckDuckGoParser()
        parser.feed(response.text)
        parser.close()
        return parser.results
    except Exception as e:
        print(f"Error fetching from DuckDuckGo: {e}")
        return []


# 6. Route to serve the HTML Frontend
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


# 7. Route to handle the API Search Request
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
        
        # If web search fails, fallback to local index
        if not web_results:
            print("Web search returned no results. Falling back to local index.")
            mode = 'local'
        else:
            # 2. Extract snippets to perform semantic ranking
            snippets = [r["snippet"] for r in web_results]
            
            # 3. Generate embeddings for query and snippets on the fly
            web_embeddings = model.encode(snippets, normalize_embeddings=True)
            query_embedding = model.encode(query, normalize_embeddings=True)
            
            # 4. Compute cosine similarity scores
            scores = np.dot(web_embeddings, query_embedding)
            
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

    # --- MODE: LOCAL (Static document index) ---
    if mode == 'local':
        query_embedding = model.encode(query, normalize_embeddings=True)
        scores = np.dot(local_embeddings, query_embedding)
        
        results = []
        for idx, score in enumerate(scores):
            results.append({
                "title": local_documents[idx]["title"],
                "text": local_documents[idx]["text"],
                "source": local_documents[idx]["source"],
                "score": float(score)
            })
            
        results = sorted(results, key=lambda x: x["score"], reverse=True)
        return jsonify(results)

if __name__ == '__main__':
    print("Starting Semantic Search Python Server at http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
