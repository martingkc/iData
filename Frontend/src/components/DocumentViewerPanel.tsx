import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { normalizeTableSpacing, resolveImageSrc } from "../utils/markdown";

const DOCUMENT_API_BASE = "http://localhost:5001";

interface DocumentViewerPanelProps {
  isOpen: boolean;
  documentId: string | null;
  documentTitle: string;
  content: string | null;
  rawText: string | null;
  isLoading: boolean;
  error: string | null;
  onClose: () => void;
}

const IconClose = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M18 6 6 18M6 6l12 12"/>
  </svg>
);

const IconDocument = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
    <line x1="16" y1="13" x2="8" y2="13"/>
    <line x1="16" y1="17" x2="8" y2="17"/>
    <polyline points="10 9 9 9 8 9"/>
  </svg>
);

const DocumentViewerPanel = ({
  isOpen,
  documentId,
  documentTitle,
  content,
  rawText,
  isLoading,
  error,
  onClose
}: DocumentViewerPanelProps) => {
  if (!isOpen) return null;

  // Custom image renderer to redirect /api/images/ URLs to agent_backend:5001
  const markdownComponents: Components = {
    img: ({ src, alt }) => {
      const imageSrc = resolveImageSrc(src, DOCUMENT_API_BASE);
      return <img src={imageSrc} alt={alt || ""} className="markdown-image" />;
    },
    table: ({ children, ...props }) => (
      <div className="markdown-table">
        <table {...props}>{children}</table>
      </div>
    ),
    th: ({ align, children, ...props }) => (
      <th {...props} style={{ textAlign: align ?? "left" }}>
        {children}
      </th>
    ),
    td: ({ align, children, ...props }) => (
      <td {...props} style={{ textAlign: align ?? "left" }}>
        {children}
      </td>
    )
  };

  return (
    <div className="document-viewer-overlay" onClick={onClose}>
      <aside className="document-viewer-panel" onClick={(e) => e.stopPropagation()}>
        <header className="document-viewer-header">
          <div className="document-viewer-title">
            <IconDocument />
            <div>
              <h2>{documentTitle || "Document"}</h2>
              {documentId && <span className="document-id">ID: {documentId}</span>}
            </div>
          </div>
          <button className="document-viewer-close" onClick={onClose} aria-label="X">
            <IconClose />
          </button>
        </header>

        <div className="document-viewer-content">
          {isLoading && (
            <div className="document-viewer-loading">
              <div className="loading-lines">
                <div className="loading-line" style={{ width: "100%" }}></div>
                <div className="loading-line" style={{ width: "85%", animationDelay: "0.1s" }}></div>
                <div className="loading-line" style={{ width: "70%", animationDelay: "0.2s" }}></div>
                <div className="loading-line" style={{ width: "90%", animationDelay: "0.3s" }}></div>
                <div className="loading-line" style={{ width: "60%", animationDelay: "0.4s" }}></div>
              </div>
            </div>
          )}

          {error && (
            <div className="document-viewer-error">
              <p>Failed to load document</p>
              <span>{error}</span>
            </div>
          )}

          {!isLoading && !error && (rawText || content) && (
            <div className="markdown-content document-markdown">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                {normalizeTableSpacing(rawText || content)}
              </ReactMarkdown>
            </div>
          )}

          {!isLoading && !error && !rawText && !content && (
            <div className="document-viewer-empty">
              <p>No content available for this document.</p>
            </div>
          )}
        </div>
      </aside>
    </div>
  );
};

export default DocumentViewerPanel;
