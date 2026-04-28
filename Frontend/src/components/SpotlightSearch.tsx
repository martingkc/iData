import { useState, useEffect, useRef, useCallback, useMemo } from "react";

const DOCUMENT_API_BASE = "http://localhost:5001";

interface SearchResult {
  chunk_id: string;
  document_id: string;
  local_path: string;
  content: string;
  raw_text: string;
  original_text?: string;
  bm25_text?: string;
  text?: string;
  chunk_index: number;
  pages: number[];
}

interface GroupedResults {
  documentName: string;
  documentId: string;
  results: SearchResult[];
}

interface FlattenedItem {
  type: "header" | "result";
  documentName?: string;
  documentId?: string;
  result?: SearchResult;
  globalIndex: number;
}

interface SpotlightSearchProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectResult: (documentId: string, chunkId: string, title: string) => void;
}

const SpotlightSearch = ({ isOpen, onClose, onSelectResult }: SpotlightSearchProps) => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [hasSearched, setHasSearched] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const formatPath = (path: string) => {
    // Remove /app/local-documents/ prefix
    return path.replace(/^\/app\/local-documents\//, "");
  };

  const getFileName = (path: string) => {
    const formatted = formatPath(path);
    const parts = formatted.split("/");
    return parts[parts.length - 1] || formatted;
  };

  // Group results by document
  const groupedResults = useMemo((): GroupedResults[] => {
    const groups: Map<string, GroupedResults> = new Map();
    
    for (const result of results) {
      const docName = getFileName(result.local_path);
      const existing = groups.get(result.document_id);
      
      if (existing) {
        existing.results.push(result);
      } else {
        groups.set(result.document_id, {
          documentName: docName,
          documentId: result.document_id,
          results: [result]
        });
      }
    }
    
    return Array.from(groups.values());
  }, [results]);

  // Flatten for keyboard navigation (only selectable items)
  const flattenedItems = useMemo((): FlattenedItem[] => {
    const items: FlattenedItem[] = [];
    let globalIndex = 0;
    
    for (const group of groupedResults) {
      for (const result of group.results) {
        items.push({
          type: "result",
          result,
          documentName: group.documentName,
          globalIndex: globalIndex++
        });
      }
    }
    
    return items;
  }, [groupedResults]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
      setQuery("");
      setResults([]);
      setSelectedIndex(0);
      setHasSearched(false);
    }
  }, [isOpen]);

  // Handle keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;
      
      if (e.key === "Escape") {
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, flattenedItems.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose, flattenedItems.length]);

  // Perform search
  const performSearch = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      setResults([]);
      setHasSearched(false);
      return;
    }

    setLoading(true);
    setHasSearched(true);
    try {
      const res = await fetch(
        `${DOCUMENT_API_BASE}/documents/search/${encodeURIComponent(searchQuery)}`,
        { credentials: "include" }
      );
      if (res.ok) {
        const data = await res.json();
        setResults(data.results || []);
        setSelectedIndex(0);
      }
    } catch (err) {
      console.error("Search error:", err);
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // If results exist and one is selected, open it
    if (flattenedItems.length > 0 && hasSearched) {
      const item = flattenedItems[selectedIndex];
      if (item?.result) {
        const displayPath = formatPath(item.result.local_path);
        onSelectResult(item.result.document_id, item.result.chunk_id, displayPath);
        onClose();
        return;
      }
    }
    // Otherwise, perform search
    performSearch(query);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);
  };

  const handleResultClick = (result: SearchResult) => {
    const displayPath = formatPath(result.local_path);
    onSelectResult(result.document_id, result.chunk_id, displayPath);
    onClose();
  };

  const truncateContent = (content: string, maxLength: number = 120) => {
    if (content.length <= maxLength) return content;
    return content.substring(0, maxLength).trim() + "…";
  };

  const getResultText = (result: SearchResult) => {
    return (
      result.raw_text ||
      result.content ||
      result.original_text ||
      result.bm25_text ||
      result.text ||
      ""
    );
  };

  if (!isOpen) return null;

  return (
    <div className="spotlight-overlay" onClick={onClose}>
      <div className="spotlight-container" onClick={(e) => e.stopPropagation()}>
        <form onSubmit={handleSubmit} className="spotlight-input-wrapper">
          <i className="fa-solid fa-magnifying-glass spotlight-icon" />
          <input
            ref={inputRef}
            type="text"
            className="spotlight-input"
            placeholder="Search documents..."
            value={query}
            onChange={handleInputChange}
            autoComplete="off"
            spellCheck={false}
          />
          {loading && <i className="fa-solid fa-spinner fa-spin spotlight-loader" />}
          <div className="spotlight-shortcut">
            <kbd>Enter</kbd> to search · <kbd>ESC</kbd> to close
          </div>
        </form>

        {groupedResults.length > 0 && (
          <div className="spotlight-results">
            {groupedResults.map((group) => (
              <div key={group.documentId} className="spotlight-group">
                <div className="spotlight-group-header">
                  <i className="fa-solid fa-file-pdf spotlight-group-icon" />
                  <span className="spotlight-group-title">{group.documentName}</span>
                  <span className="spotlight-group-count">{group.results.length} match{group.results.length !== 1 ? "es" : ""}</span>
                </div>
                <div className="spotlight-group-items">
                  {group.results.map((result) => {
                    const itemIndex = flattenedItems.findIndex(
                      (item) => item.result?.chunk_id === result.chunk_id
                    );
                    return (
                      <div
                        key={result.chunk_id}
                        className={`spotlight-result-item ${itemIndex === selectedIndex ? "selected" : ""}`}
                        onClick={() => handleResultClick(result)}
                        onMouseEnter={() => setSelectedIndex(itemIndex)}
                      >
                        <div className="spotlight-result-meta">
                          {result.pages && result.pages.length > 0 && (
                            <span className="spotlight-result-page">
                              <i className="fa-regular fa-bookmark" /> Page {result.pages[0]}
                            </span>
                          )}
                          <span className="spotlight-result-chunk">Chunk {result.chunk_index + 1}</span>
                        </div>
                        <p className="spotlight-result-content">{truncateContent(getResultText(result))}</p>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}

        {hasSearched && !loading && results.length === 0 && (
          <div className="spotlight-no-results">
            <i className="fa-solid fa-circle-exclamation" />
            <span>No results found for "{query}"</span>
          </div>
        )}

        {hasSearched && !loading && results.length > 0 && (
          <div className="spotlight-footer">
            <span>{results.length} result{results.length !== 1 ? "s" : ""} in {groupedResults.length} document{groupedResults.length !== 1 ? "s" : ""}</span>
            <span className="spotlight-footer-hint">
              <kbd>↑</kbd><kbd>↓</kbd> navigate · <kbd>Enter</kbd> open
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

export default SpotlightSearch;
