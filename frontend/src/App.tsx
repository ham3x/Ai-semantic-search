import React, { useState, useEffect } from 'react';

// Define structure for search API output
interface SearchResult {
  title: string;
  text: string;
  source: string;
  score: number;
}

export default function App() {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<'web' | 'local'>('web');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // States for document upload and ChromaDB status
  const [uploading, setUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadedFilenames, setUploadedFilenames] = useState<string[]>([]);
  const [uploadedChunksCount, setUploadedChunksCount] = useState<number>(0);

  // Fetch current upload status and populate file list
  const refreshUploadStatus = async () => {
    try {
      const response = await fetch('/api/upload/status');
      if (response.ok) {
        const data = await response.json();
        if (data.uploaded) {
          setUploadedFilenames(data.filenames || []);
          setUploadedChunksCount(data.chunks_count || 0);
          setUploadSuccess(`Database active: ${data.filenames.length} file(s) loaded (${data.chunks_count} sections total).`);
        } else {
          setUploadedFilenames([]);
          setUploadedChunksCount(0);
          setUploadSuccess(null);
        }
      }
    } catch (err) {
      console.error("Failed to fetch upload status:", err);
    }
  };

  // Check upload status on initial mount
  useEffect(() => {
    refreshUploadStatus();
  }, []);

  // Trigger API search
  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const trimmedQuery = query.trim();
    if (!trimmedQuery) return;

    setLoading(true);
    setError(null);
    setSearched(true);
    setResults([]);

    try {
      // Fetch similarity scores from the Python Flask backend with q and mode parameters
      const response = await fetch(`/api/search?q=${encodeURIComponent(trimmedQuery)}&mode=${mode}`);
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || 'API server returned an error');
      }
      const data = await response.json();
      setResults(data);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Could not connect to the Python backend server. Make sure it is running on port 5002.');
    } finally {
      setLoading(false);
    }
  };

  // Handle file uploads (PDF, DOCX, CSV, TXT, etc.)
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const file = files[0];

    setUploading(true);
    setUploadSuccess(null);
    setUploadError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || 'Failed to upload document');
      }
      
      await refreshUploadStatus();
      setUploadSuccess(`Successfully parsed and loaded ${data.chunks_count} sections from '${data.filename}'.`);
      setMode('local'); // Automatically switch to local database mode
    } catch (err: any) {
      console.error(err);
      setUploadError(err.message || 'Failed to connect/upload document.');
    } finally {
      setUploading(false);
      // Reset input value to allow uploading the same file again if needed
      e.target.value = '';
    }
  };

  // Delete a specific file from the collection
  const deleteFile = async (filename: string) => {
    setUploadSuccess(null);
    setUploadError(null);
    try {
      const response = await fetch('/api/upload/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || 'Failed to delete file');
      }
      await refreshUploadStatus();
    } catch (err: any) {
      console.error(err);
      setUploadError(err.message || 'Failed to delete file.');
    }
  };

  // Clear all files from the collection
  const clearDatabase = async () => {
    if (!window.confirm("Are you sure you want to clear all documents from the database?")) return;
    setUploadSuccess(null);
    setUploadError(null);
    try {
      const response = await fetch('/api/upload/clear', {
        method: 'POST',
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || 'Failed to clear database');
      }
      setUploadedFilenames([]);
      setUploadedChunksCount(0);
      setUploadSuccess("Database cleared successfully.");
    } catch (err: any) {
      console.error(err);
      setUploadError(err.message || 'Failed to clear database.');
    }
  };

  const isSearchDisabled = mode === 'local' && uploadedFilenames.length === 0;

  return (
    <div style={styles.appContainer}>
      <header style={styles.header}>
        <h1 style={styles.title}>AI Web Search Engine</h1>
        <p style={styles.subtitle}>
          Reranks live web search results or queries your custom local database in real-time using a local SentenceTransformer model.
        </p>
      </header>

      {/* Main Console */}
      <main style={styles.card}>
        {/* Mode Selector Tabs */}
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
          <button
            type="button"
            onClick={() => setMode('local')}
            style={{
              ...styles.tabButton,
              backgroundColor: mode === 'local' ? 'rgba(139, 92, 246, 0.15)' : 'transparent',
              borderColor: mode === 'local' ? 'var(--accent-color)' : 'transparent',
              color: mode === 'local' ? '#fff' : 'var(--text-muted)',
            }}
          >
            📁 Local Database
          </button>
        </div>

        {/* Document Upload Area (visible when local mode is active) */}
        {mode === 'local' && (
          <div style={styles.uploadSection}>
            <div style={styles.uploadHeader}>
              <span style={{ fontSize: '0.95rem', fontWeight: 600 }}>
                {uploadedFilenames.length > 0 
                  ? `Active Database Documents (${uploadedFilenames.length}) — ${uploadedChunksCount} sections:` 
                  : 'Local Database Setup'}
              </span>
              {uploadedFilenames.length > 0 && (
                <button
                  type="button"
                  onClick={clearDatabase}
                  className="clear-btn-hover"
                  style={styles.clearAllBtn}
                >
                  Clear All
                </button>
              )}
            </div>

            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', lineHeight: '1.4' }}>
              Populate your local database by uploading files (supports <strong>PDF, DOCX, CSV, TXT</strong>). Each file is chunked, embedded, and indexed locally inside ChromaDB for semantic search.
            </p>

            {/* List of uploaded files */}
            {uploadedFilenames.length > 0 && (
              <div style={styles.filesList}>
                {uploadedFilenames.map((name) => (
                  <div key={name} style={styles.fileItem}>
                    <span style={styles.fileItemText} title={name}>📄 {name}</span>
                    <button
                      type="button"
                      onClick={() => deleteFile(name)}
                      className="delete-btn-hover"
                      style={styles.deleteFileBtn}
                      title={`Remove '${name}'`}
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}
            
            <div style={styles.uploadControls}>
              <label 
                className="upload-label-hover"
                style={{
                  ...styles.uploadLabel,
                  opacity: uploading ? 0.6 : 1,
                  pointerEvents: uploading ? 'none' : 'auto'
                }}
              >
                {uploading ? 'Processing File...' : 'Upload Document'}
                <input
                  type="file"
                  accept=".pdf,.docx,.csv,.txt,.md,.json"
                  onChange={handleFileUpload}
                  style={{ display: 'none' }}
                  disabled={uploading}
                />
              </label>
              {uploading && <div style={styles.miniSpinner}></div>}
            </div>

            {uploadSuccess && (
              <div style={styles.uploadSuccessMsg}>
                ✓ {uploadSuccess}
              </div>
            )}

            {uploadError && (
              <div style={styles.uploadErrorMsg}>
                ⚠ {uploadError}
              </div>
            )}
          </div>
        )}

        {/* Search Input Box Form */}
        <form onSubmit={handleSearch} style={styles.searchBar}>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{
              ...styles.inputText,
              opacity: isSearchDisabled ? 0.6 : 1,
              cursor: isSearchDisabled ? 'not-allowed' : 'text',
            }}
            disabled={isSearchDisabled}
            placeholder={
              isSearchDisabled
                ? "Please upload a document (.pdf, .docx, .csv, .txt) above to start searching..."
                : mode === 'web'
                ? "Search the web for anything (e.g. 'new space telescopes', 'best pasta recipe')..."
                : `Search inside ${uploadedFilenames.length} loaded file(s)...`
            }
          />
          <button
            type="submit"
            style={{
              ...styles.btn,
              opacity: isSearchDisabled ? 0.6 : 1,
              cursor: isSearchDisabled ? 'not-allowed' : 'pointer',
            }}
            disabled={isSearchDisabled}
          >
            Search
          </button>
        </form>

        {/* Loading Spinner */}
        {loading && (
          <div style={styles.loaderContainer}>
            <div style={styles.spinner}></div>
            <p style={{ color: 'var(--text-muted)' }}>
              {mode === 'web'
                ? "Fetching web results and computing semantic embeddings..."
                : "Querying ChromaDB database and performing cross-document semantic search..."}
            </p>
          </div>
        )}

        {/* Error Alert */}
        {error && (
          <div style={styles.errorContainer}>
            <p>{error}</p>
          </div>
        )}

        {/* Results Render List */}
        {!loading && !error && searched && results.length === 0 && (
          <div style={styles.noResults}>No matches found. Try another query.</div>
        )}

        {!loading && !error && !searched && (
          <div style={styles.noResults}>
            {mode === 'web'
              ? "Enter a question to search the web with real-time AI relevance reranking."
              : uploadedFilenames.length > 0
              ? `Ask a question to query your ${uploadedFilenames.length} loaded document(s) semantically.`
              : "Upload documents above to populate your local database."}
          </div>
        )}

        {!loading && !error && results.length > 0 && (
          <div style={styles.resultsList}>
            {results.map((item, index) => {
              const scorePercent = (item.score * 100).toFixed(1);
              const isMediumScore = item.score < 0.35;

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

                  <p style={styles.resultText}>{item.text}</p>

                  {/* Similarity Progress Bar */}
                  <div style={styles.scoreBarBg}>
                    <div
                      style={{
                        ...styles.scoreBarFill,
                        width: `${Math.max(0, Math.min(100, item.score * 100))}%`,
                      }}
                    ></div>
                  </div>

                  {/* Citation / Source link */}
                  <div style={styles.sourceContainer}>
                    <span style={{ fontSize: '0.8rem' }}>Source citation:</span>
                    {item.source.startsWith('http') ? (
                      <a
                        href={item.source}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={styles.sourceLink}
                      >
                        {item.source}
                      </a>
                    ) : (
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.82rem', fontWeight: 500 }}>
                        {item.source}
                      </span>
                    )}
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

// Inline styling system for premium appearance
const styles: Record<string, React.CSSProperties> = {
  appContainer: {
    width: '100%',
    maxWidth: '750px',
    padding: '20px 0',
    display: 'flex',
    flexDirection: 'column',
    gap: '32px',
  },
  header: {
    textAlign: 'center',
  },
  title: {
    fontSize: '2.5rem',
    fontWeight: 700,
    background: 'linear-gradient(135deg, #fff 40%, var(--text-muted) 100%)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    marginBottom: '8px',
  },
  subtitle: {
    color: 'var(--text-muted)',
    fontSize: '1rem',
    lineHeight: '1.5',
  },
  card: {
    background: 'var(--panel-bg)',
    backdropFilter: 'blur(12px)',
    WebkitBackdropFilter: 'blur(12px)',
    border: '1px solid var(--panel-border)',
    borderRadius: '16px',
    padding: '28px',
    boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.3)',
    display: 'flex',
    flexDirection: 'column',
    gap: '24px',
  },
  modeTabs: {
    display: 'flex',
    gap: '10px',
    borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
    paddingBottom: '12px',
  },
  tabButton: {
    border: '1px solid transparent',
    borderRadius: '8px',
    padding: '8px 16px',
    fontSize: '0.9rem',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  },
  uploadSection: {
    background: 'rgba(255, 255, 255, 0.02)',
    border: '1px dashed rgba(255, 255, 255, 0.1)',
    borderRadius: '12px',
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
    transition: 'all 0.3s ease',
  },
  uploadHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '8px',
  },
  clearAllBtn: {
    background: 'rgba(244, 63, 94, 0.1)',
    border: '1px solid rgba(244, 63, 94, 0.2)',
    color: 'var(--error)',
    borderRadius: '6px',
    padding: '4px 10px',
    fontSize: '0.78rem',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  },
  filesList: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '8px',
    margin: '4px 0',
  },
  fileItem: {
    background: 'rgba(255, 255, 255, 0.03)',
    border: '1px solid rgba(255, 255, 255, 0.06)',
    borderRadius: '8px',
    padding: '6px 12px',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    transition: 'all 0.2s ease',
  },
  fileItemText: {
    fontSize: '0.82rem',
    fontWeight: 500,
    color: '#d1d5db',
    maxWidth: '180px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  deleteFileBtn: {
    background: 'transparent',
    border: 'none',
    color: 'var(--text-muted)',
    fontSize: '0.75rem',
    cursor: 'pointer',
    fontWeight: 'bold',
    padding: '2px 4px',
    borderRadius: '4px',
    transition: 'all 0.15s ease',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  uploadControls: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  uploadLabel: {
    background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.2) 0%, rgba(6, 182, 212, 0.2) 100%)',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    color: '#fff',
    padding: '10px 18px',
    borderRadius: '8px',
    fontSize: '0.88rem',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    textAlign: 'center',
    display: 'inline-block',
  },
  miniSpinner: {
    border: '2px solid rgba(255, 255, 255, 0.05)',
    borderTop: '2px solid var(--accent-secondary)',
    borderRadius: '50%',
    width: '16px',
    height: '16px',
    animation: 'spin 1s linear infinite',
  },
  uploadSuccessMsg: {
    color: 'var(--success)',
    fontSize: '0.85rem',
    fontWeight: 500,
  },
  uploadErrorMsg: {
    color: 'var(--error)',
    fontSize: '0.85rem',
    fontWeight: 500,
  },
  searchBar: {
    display: 'flex',
    gap: '12px',
    width: '100%',
  },
  inputText: {
    flex: 1,
    background: 'rgba(0, 0, 0, 0.35)',
    border: '1px solid var(--panel-border)',
    borderRadius: '10px',
    color: '#fff',
    padding: '16px 20px',
    fontSize: '1.05rem',
    outline: 'none',
    transition: 'all 0.3s ease',
  },
  btn: {
    background: 'var(--accent-color)',
    color: '#fff',
    border: 'none',
    borderRadius: '10px',
    padding: '16px 30px',
    fontSize: '1.05rem',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    whiteSpace: 'nowrap',
  },
  loaderContainer: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '12px',
    padding: '30px 0',
  },
  spinner: {
    border: '3px solid rgba(255, 255, 255, 0.05)',
    borderTop: '3px solid var(--accent-color)',
    borderRadius: '50%',
    width: '28px',
    height: '28px',
    animation: 'spin 1s linear infinite',
  },
  errorContainer: {
    background: 'rgba(244, 63, 94, 0.1)',
    border: '1px solid rgba(244, 63, 94, 0.2)',
    color: 'var(--error)',
    borderRadius: '8px',
    padding: '14px 18px',
    fontSize: '0.95rem',
  },
  noResults: {
    textAlign: 'center',
    padding: '40px 0',
    color: 'var(--text-muted)',
    fontSize: '0.95rem',
  },
  resultsList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    animation: 'fadeIn 0.35s ease',
  },
  resultCard: {
    background: 'rgba(255, 255, 255, 0.02)',
    border: '1px solid rgba(255, 255, 255, 0.05)',
    borderRadius: '12px',
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
    transition: 'all 0.3s ease',
  },
  resultHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '10px',
  },
  resultTitle: {
    fontSize: '1.2rem',
    fontWeight: 600,
    color: '#fff',
  },
  badge: {
    padding: '4px 10px',
    borderRadius: '20px',
    fontSize: '0.8rem',
    fontWeight: 700,
    border: '1px solid',
    whiteSpace: 'nowrap',
  },
  resultText: {
    fontSize: '0.95rem',
    lineHeight: '1.6',
    color: '#d1d5db',
  },
  scoreBarBg: {
    height: '4px',
    background: 'rgba(255, 255, 255, 0.05)',
    borderRadius: '2px',
    overflow: 'hidden',
  },
  scoreBarFill: {
    height: '100%',
    background: 'linear-gradient(90deg, var(--accent-color), var(--accent-secondary))',
    borderRadius: '2px',
    transition: 'width 0.8s cubic-bezier(0.4, 0, 0.2, 1)',
  },
  sourceContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    borderTop: '1px solid rgba(255, 255, 255, 0.05)',
    paddingTop: '12px',
    marginTop: '4px',
  },
  sourceLink: {
    color: 'var(--accent-secondary)',
    textDecoration: 'none',
    fontSize: '0.82rem',
    fontWeight: 500,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
};

// Add standard keyframe spin styles for loading spinner and custom interactive styles
if (typeof document !== 'undefined') {
  const style = document.createElement('style');
  style.innerHTML = `
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
    .delete-btn-hover:hover {
      background-color: rgba(244, 63, 94, 0.2) !important;
      color: #f43f5e !important;
    }
    .clear-btn-hover:hover {
      background-color: rgba(244, 63, 94, 0.2) !important;
      border-color: rgba(244, 63, 94, 0.4) !important;
    }
    .upload-label-hover:hover {
      border-color: rgba(255, 255, 255, 0.2) !important;
      box-shadow: 0 0 12px var(--accent-glow) !important;
    }
  `;
  document.head.appendChild(style);
}
