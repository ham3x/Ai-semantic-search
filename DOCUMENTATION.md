# AI Web Search Engine: Comprehensive Code Explanation

This document provides a line-by-line explanation of the AI-powered Web Search Engine codebase. The application is built using a **Python (Flask) backend** for real-time web scraping and semantic reranking using a local SentenceTransformer model, and a **Vite + React (TypeScript) frontend** for a responsive, interactive user interface.

---

## Table of Contents
1. [Backend: `app.py`](#backend-apppy)
2. [Frontend: `src/App.tsx`](#frontend-srcapptsx)
3. [Vite Configuration: `vite.config.ts`](#vite-configuration-viteconfigts)
4. [How to Import into Google Docs](#how-to-import-into-google-docs)

---

## Backend: `app.py`

This file handles model loading, web scraping, semantic vector calculations, and serves the static React build files.

### 1. Imports
```python
import os
```
* **Line 1:** Imports Python's built-in `os` library for directory and path resolution.

```python
from flask import Flask, request, jsonify, send_from_directory
```
* **Line 2:** Imports Flask API functions:
  * `Flask`: To initialize the server application.
  * `request`: To parse incoming HTTP query parameters (e.g. `?q=query&mode=web`).
  * `jsonify`: To serialize Python lists/dictionaries into standard JSON.
  * `send_from_directory`: To securely serve the frontend files from the compiled build folder.

```python
from flask_cors import CORS
```
* **Line 3:** Imports CORS helper to enable safe API requests from different local ports (e.g., React on port 3000 calling Flask on port 5000) during development.

```python
from sentence_transformers import SentenceTransformer
```
* **Line 4:** Imports `SentenceTransformer` from Hugging Face's SentenceTransformers library, which downloads and executes the vector embedding model.

```python
import numpy as np
```
* **Line 5:** Imports NumPy for highly optimized matrix dot product calculations (used to calculate cosine similarity).

```python
import requests
```
* **Line 6:** Imports the HTTP client library `requests` to make standard network calls to DuckDuckGo.

```python
from html.parser import HTMLParser
```
* **Line 7:** Imports the standard library HTML parser class to inspect raw webpage responses.

```python
from urllib.parse import unquote, urlparse, parse_qs
```
* **Line 8:** Imports URL utilities to parse and clean up query strings and redirect parameters.

### 2. Initialization & Setup
```python
# 1. Initialize Flask App and Enable CORS
app = Flask(__name__, static_folder='frontend/dist', static_url_path='')
```
* **Line 11:** Initializes the Flask application. `static_folder='frontend/dist'` tells Flask that compiled frontend assets reside in the `frontend/dist` folder. `static_url_path=''` maps these assets directly to the root URL (meaning `/assets/index.js` serves from the static directory).

```python
CORS(app)  # Allows the frontend to make API calls to this backend safely
```
* **Line 12:** Activates CORS protocols across all Flask endpoints.

```python
# 2. Load the Lightweight Semantic Search Model
model = SentenceTransformer('all-MiniLM-L6-v2')
```
* **Line 16:** Loads the pre-trained `all-MiniLM-L6-v2` AI model (approx. 80MB). This runs completely offline on your CPU.

### 3. Local Database Definition
```python
local_documents = [
    {
        "title": "Theory of Relativity",
        "text": "Albert Einstein developed the theory... spacetime.",
        "source": "https://en.wikipedia.org/wiki/Theory_of_relativity"
    },
    ...
]
```
* **Lines 19-43:** Defines a hardcoded fallback database of documents. Each document contains a title, text paragraph (analyzed by the AI), and source URL citation.

```python
local_texts = [doc["text"] for doc in local_documents]
local_embeddings = model.encode(local_texts, normalize_embeddings=True)
```
* **Lines 46-47:** Isolates the text strings and precomputes their vector coordinates on server startup. `normalize_embeddings=True` standardizes vector lengths to `1.0` so similarity is computable via a dot product.

### 4. Custom DuckDuckGo Web Scraper
```python
class DuckDuckGoParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self.current_result = None
        self.in_title = False
        self.in_snippet = False
```
* **Lines 53-59:** Creates a flat parser class. `self.results` stores parsed items. `self.current_result` is a temporary dict. `self.in_title` and `self.in_snippet` track tag positions.

```python
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = attrs_dict.get('class', '')
```
* **Lines 61-63:** Runs whenever an HTML start tag is parsed. Converts its attributes (like `class`, `href`) to a dictionary.

```python
        if tag == 'a' and 'result__a' in classes:
            if self.current_result:
                self.results.append(self.current_result)
```
* **Lines 66-68:** Detects a result title anchor tag (`<a class="result__a">`). If `self.current_result` was already populated with a previous item, it saves it first.

```python
            href = attrs_dict.get('href', '')
            if 'uddg=' in href:
                parsed = urlparse(href)
                qs = parse_qs(parsed.query)
                if 'uddg' in qs:
                    href = qs['uddg'][0]
```
* **Lines 70-75:** Extracts the destination link. Cleans it if it's nested in a DuckDuckGo redirect query parameter (`uddg`).

```python
            self.current_result = {
                "title": "",
                "url": href,
                "snippet": ""
            }
            self.in_title = True
```
* **Lines 77-82:** Creates a new result object with empty fields, stores the cleaned URL, and flags the parser to collect the text inside the anchor.

```python
        elif tag == 'a' and 'result__snippet' in classes:
            self.in_snippet = True
```
* **Lines 85-86:** Identifies the description snippet tag (`<a class="result__snippet">`) and enables the snippet-collection flag.

```python
    def handle_endtag(self, tag):
        if tag == 'a':
            self.in_title = False
            self.in_snippet = False
```
* **Lines 88-91:** Runs when closing tags are reached (e.g. `</a>`), disabling data collection flags.

```python
    def handle_data(self, data):
        if self.in_title and self.current_result:
            self.current_result["title"] += data
        elif self.in_snippet and self.current_result:
            self.current_result["snippet"] += data
```
* **Lines 93-97:** Captures text between tags and appends it to either the title or snippet property of `self.current_result`.

```python
    def close(self):
        super().close()
        if self.current_result:
            self.results.append(self.current_result)
```
* **Lines 99-102:** Triggered when parsing ends, ensuring the final parsed item is saved to `self.results`.

```python
def search_ddg_html(query):
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)..."
    }
    params = {"q": query}
```
* **Lines 105-110:** Defines parameters to query the static HTML version of DuckDuckGo. Uses a fake Chrome User-Agent header to bypass rate limits.

```python
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
```
* **Lines 111-122:** Submits a GET request. Feeds the HTML string response into our custom parser class, returning parsed result dicts.

### 5. Serving Routes & Search Logic
```python
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')
```
* **Lines 126-128:** Serves the index HTML of the compiled React client when visiting `http://localhost:5000/`.

```python
@app.route('/api/search', methods=['GET'])
def search_api():
    query = request.args.get('q', '').strip()
    mode = request.args.get('mode', 'web').strip()
```
* **Lines 132-135:** Sets up the `/api/search` endpoint. Reads the search string `q` and search scope `mode`.

```python
    if mode == 'web':
        web_results = search_ddg_html(query)
        if not web_results:
            mode = 'local'
```
* **Lines 141-146:** In Web Mode, queries DuckDuckGo. If it fails, falls back to Local Mode.

```python
        else:
            snippets = [r["snippet"] for r in web_results]
            web_embeddings = model.encode(snippets, normalize_embeddings=True)
            query_embedding = model.encode(query, normalize_embeddings=True)
```
* **Lines 148-150:** Converts the live snippets and user query into normalized vector embeddings.

```python
            scores = np.dot(web_embeddings, query_embedding)
```
* **Line 153:** Computes the cosine similarity scores using a dot product.

```python
            results = []
            for idx, score in enumerate(scores):
                results.append({
                    "title": web_results[idx]["title"],
                    "text": web_results[idx]["snippet"],
                    "source": web_results[idx]["url"],
                    "score": float(score)
                })
```
* **Lines 156-163:** Combines web results with relevance scores, converting the NumPy float32 value into a standard Python float.

```python
            results = sorted(results, key=lambda x: x["score"], reverse=True)
            return jsonify(results)
```
* **Lines 165-166:** Sorts results by highest relevance score first and returns JSON.

```python
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
```
* **Lines 169-181:** Local Mode semantic search logic. Employs the pre-computed document embeddings to calculate similarities and return sorted results.

---

## Frontend: `src/App.tsx`

The React component manages interface state, fetches API data, and renders interactive citation components.

```typescript
import React, { useState } from 'react';
```
* **Line 1:** Imports React core and `useState` for UI state tracking.

```typescript
interface SearchResult {
  title: string;
  text: string;
  source: string;
  score: number;
}
```
* **Lines 4-9:** Enforces typings for backend search result data.

```typescript
export default function App() {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<'web' | 'local'>('web');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
```
* **Lines 12-17:** Declares React states to store the text input (`query`), search mode (`mode`), loading indicator (`loading`), results arrays (`results`), search status (`searched`), and connection status (`error`).

```typescript
  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const trimmedQuery = query.trim();
    if (!trimmedQuery) return;

    setLoading(true);
    setError(null);
    setSearched(true);
    setResults([]);
```
* **Lines 20-29:** Handler for form submissions. Stops page reloads (`e.preventDefault()`), validates query text, resets states, and clears results.

```typescript
    try {
      const response = await fetch(`/api/search?q=${encodeURIComponent(trimmedQuery)}&mode=${mode}`);
      if (!response.ok) {
        throw new Error('API server returned an error');
      }
      const data = await response.json();
      setResults(data);
    } catch (err) {
      console.error(err);
      setError('Could not connect to the Python backend server...');
    } finally {
      setLoading(false);
    }
  };
```
* **Lines 31-43:** Performs HTTP request. Resolves data, catches server offline states, and ensures the loading spinner closes at the end.

```typescript
  return (
    <div style={styles.appContainer}>
      <header style={styles.header}>
        <h1 style={styles.title}>AI Web Search Engine</h1>
        <p style={styles.subtitle}>...</p>
      </header>
```
* **Lines 46-53:** Main JSX wrapper. Applies styling layout attributes.

```typescript
      <main style={styles.card}>
        <div style={styles.modeTabs}>
          <button
            type="button"
            onClick={() => setMode('web')}
            style={{
              ...styles.tabButton,
              backgroundColor: mode === 'web' ? 'rgba(139, 92, 246, 0.15)' : 'transparent',
              borderColor: mode === 'web' ? 'var(--accent-color)' : 'transparent',
              color: mode === 'web' ? '#fff' : 'var(--text-muted)',
            }}
          >
            🛜 Web Search (AI-Reranked)
          </button>
```
* **Lines 56-72:** Renders the "Web Search" button. Sets mode to `'web'` on click. Dynamically changes borders/colors based on active state.

```typescript
          <button
            type="button"
            onClick={() => setMode('local')}
            style={{ ... }}
          >
            📁 Local Database
          </button>
```
* **Lines 73-86:** Renders the "Local Database" toggle button.

```typescript
        <form onSubmit={handleSearch} style={styles.searchBar}>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={styles.inputText}
            placeholder={ mode === 'web' ? "Search web..." : "Search local..." }
          />
          <button type="submit" style={styles.btn}>Search</button>
        </form>
```
* **Lines 89-105:** Search submission form. Uses input box value and dynamically sets placeholder text depending on the mode.

```typescript
        {loading && (
          <div style={styles.loaderContainer}>
            <div style={styles.spinner}></div>
            <p style={{ color: 'var(--text-muted)' }}>...</p>
          </div>
        )}
```
* **Lines 108-117:** Shows loading animations and descriptions.

```typescript
        {error && (
          <div style={styles.errorContainer}>
            <p>{error}</p>
          </div>
        )}
```
* **Lines 120-124:** Renders the connection error warning card.

```typescript
        {!loading && !error && searched && results.length === 0 && (
          <div style={styles.noResults}>No matches found.</div>
        )}

        {!loading && !error && !searched && (
          <div style={styles.noResults}>...</div>
        )}
```
* **Lines 127-135:** Renders help/empty messages.

```typescript
        {!loading && !error && results.length > 0 && (
          <div style={styles.resultsList}>
            {results.map((item, index) => {
              const scorePercent = (item.score * 100).toFixed(1);
              const isMediumScore = item.score < 0.35;
```
* **Lines 137-142:** Iterates over the results to render citation cards.

```typescript
              return (
                <div key={index} style={styles.resultCard}>
                  <div style={styles.resultHeader}>
                    <h3 style={styles.resultTitle}>{item.title}</h3>
                    <span
                      style={{
                        ...styles.badge,
                        backgroundColor: isMediumScore ? 'rgba(245, 158, 11, 0.12)' : 'rgba(16, 185, 129, 0.12)',
                        color: isMediumScore ? '#f59e0b' : 'var(--success)',
                        borderColor: isMediumScore ? 'rgba(245, 158, 11, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                      }}
                    >
                      Relevance: {scorePercent}%
                    </span>
                  </div>
```
* **Lines 144-161:** Structure of result card. The tag switches color scheme to amber (`isMediumScore`) if the relevance score falls below 35%.

```typescript
                  <p style={styles.resultText}>{item.text}</p>
```
* **Lines 163:** Displays the text content citation.

```typescript
                  <div style={styles.scoreBarBg}>
                    <div
                      style={{
                        ...styles.scoreBarFill,
                        width: `${Math.max(0, Math.min(100, item.score * 100))}%`,
                      }}
                    ></div>
                  </div>
```
* **Lines 166-172:** Progress bar score container. Computes width using similarity percentage.

```typescript
                  <div style={styles.sourceContainer}>
                    <span style={{ fontSize: '0.8rem' }}>Source citation:</span>
                    <a
                      href={item.source}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={styles.sourceLink}
                    >
                      {item.source}
                    </a>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
```
* **Lines 175-194:** Source link citation wrapper. Uses `target="_blank"` and `rel="noopener noreferrer"` to load links safely in new browser tabs.

---

## Vite Configuration: `vite.config.ts`

Configures compiling rules and local development proxy options.

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
```
* **Lines 1-2:** Imports Vite config builder and Vite React compiler plugin.

```typescript
export default defineConfig({
  plugins: [react()],
```
* **Lines 5-6:** Activates the React plugin to bundle typescript files into compressed javascript assets.

```typescript
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
```
* **Lines 7-17:** Sets local Vite dev server port to 3000. Sets up proxy: any frontend requests matching `/api/*` are redirected to `http://127.0.0.1:5000` to prevent CORS security blocks during development.

---

## How to Import into Google Docs

Since this file is saved in standard **Markdown (.md)** format, you can easily import it into Google Docs:

1. **Direct Copy-Paste:**
   * Open this [DOCUMENTATION.md](file:///Users/hamadalmeghewli/Code/semantic-search-demo/DOCUMENTATION.md) file.
   * Press `Cmd + A` (Mac) to select all text, then `Cmd + C` to copy.
   * Create a new Google Doc and press `Cmd + V` to paste. Google Docs automatically converts Markdown headings, list blocks, and code formatting!
2. **File Upload (Google Drive):**
   * Upload [DOCUMENTATION.md](file:///Users/hamadalmeghewli/Code/semantic-search-demo/DOCUMENTATION.md) to Google Drive.
   * Right-click the file in Google Drive, select **Open with** -> **Google Docs**. Google Docs will convert the file into an editable document instantly.
