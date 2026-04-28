import { FormEvent, useRef, useEffect, useState, useCallback, forwardRef, useImperativeHandle } from "react";
import ReactMarkdown, { Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChatMessage, SelectedDoc } from "../types";
import DocumentViewerPanel from "./DocumentViewerPanel";
import GraphRenderer from "./GraphRenderer";
import { parseGraphContent } from "../utils/graphParser";
import { normalizeTableSpacing, resolveImageSrc } from "../utils/markdown";

const DOCUMENT_API_BASE = "http://localhost:5001";

interface ChatWindowProps {
  messages: ChatMessage[];
  onSend: (content: string) => void;
  isStreaming: boolean;
  modelOptions: string[];
  selectedModel: string;
  onModelChange: (model: string) => void;
  onCreateChat: () => void;
  onOpenToolModal: () => void;
  onToggleDeepThinking: () => void;
  deepThinkingEnabled: boolean;
  selectedDocs: SelectedDoc[];
  onToggleDocMenu: () => void;
  docMenuOpen: boolean;
  onOpenFileManager: () => void;
  onOpenAddDocs: () => void;
  onRetryMessage: (messageId: string) => void;
}

export interface ChatWindowRef {
  openDocViewer: (documentId: string, chunkId: string | null, title: string) => void;
}

const roleLabel: Record<ChatMessage["role"], string> = {
  user: "You",
  assistant: "Assistant",
  system: "System"
};

const firstNonEmptyString = (...values: unknown[]): string | null => {
  for (const value of values) {
    if (typeof value === "string") {
      const trimmed = value.trim();
      if (trimmed.length > 0) {
        return trimmed;
      }
    }
  }
  return null;
};

const IconPlus = () => (
  <svg className="chat-icon" viewBox="0 0 24 24" aria-hidden="true">
    <path
      d="M12 5v14m7-7H5"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);




const IconSearch = () => (
  <svg className="chat-icon" viewBox="0 0 24 24" aria-hidden="true">
    <circle cx="11" cy="11" r="6" stroke="currentColor" strokeWidth="1.6" fill="none" />
    <path d="M17 17l4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
  </svg>
);

const IconFolder = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path
      fillRule="evenodd"
      clipRule="evenodd"
      d="M4 4H12V6H20H22V8L22 18V20L20 20H4L2 20V18V6V4H4ZM20 8H10V6H4V18H20V8Z"
      fill="currentColor"
    />
  </svg>
);

const IconFile = () => (
  <svg className="chip-icon" viewBox="0 0 24 24" aria-hidden="true">
    <path
      d="M8 3h6l5 5v11a2 2 0 01-2 2H8a2 2 0 01-2-2V5a2 2 0 012-2z"
      stroke="currentColor"
      strokeWidth="1.4"
      fill="currentColor"
    />
    <path d="M14 3v5h5" stroke="currentColor" strokeWidth="1.4" fill="none" />
  </svg>
);

const IconSend = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path
      fillRule="evenodd"
      clipRule="evenodd"
      d="M18 16H8V18H6V16H4V14H6V12H8V14H18V4H20V14V16H18ZM8 12V10H10V12H8ZM8 18V20H10V18H8Z"
      fill="currentColor"
    />
  </svg>
);

const IconGear = () => (
  <svg xmlns="http://www.w3.org/2000/svg" version="1.1" height="18" width="18" viewBox="3.6645970344543457 3.680098295211792 92.3938980102539 92.3938980102539"><path d="m43.266 92.754v-3.3008h-6.6016v-6.6016h-6.6016v6.6016h-13.195v-6.6016h-6.6016v-13.195h6.6016v-6.6016h-6.6016v-6.6016h-6.6016v-13.195h6.6016v-6.6016h6.6016v-6.6016h-6.6016l0.007813-6.582v-6.5977h6.6016v-6.5977h13.195v6.6016h6.6016l-0.003906-3.3047v-3.2969h6.6016l-0.003906-3.3008v-3.2969h13.195v6.6016h6.6016v6.6016h6.6016l-0.003906-3.3086v-3.2969h13.195v6.6016h6.6016v13.195h-6.6016v6.6016h6.6016v6.6016h6.6016v13.195h-6.6016v6.6016h-6.6016v6.6016h6.6016v13.195h-6.6016v6.6016h-13.195v-6.6016h-6.6016v6.6016h-6.6016v6.6016h-13.195zm13.195-9.8984v-6.5977h13.195v6.6016h13.195v-13.195h-6.6016v-13.195h13.195v-13.195h-13.195v-13.195h6.6016l0.003907-6.6055v-6.5977h-13.195v6.6016h-13.195v-13.199h-13.195v13.195h-13.195l-0.003907-3.2969v-3.3008h-13.195v13.195h6.6016v13.195h-13.195v13.195h13.195v13.195h-6.6016v13.195h13.195v-6.6016h13.195v13.195h13.195zm-13.195-16.496v-3.3008h-6.6016v-6.6016h-6.6016v-13.195h6.6016v-6.6016h6.6016v-6.6016h13.195v6.6016h6.6016v6.6016h6.6016v13.195h-6.6016v6.6016h-6.6016v6.6016h-13.195zm13.195-6.5977v-3.3008h6.6016v-13.195h-6.6016v-6.6016h-13.195v6.6016h-6.6016v13.195h6.6016v6.6016h13.195z" fill="currentColor"/></svg>
);


const ChatWindow = forwardRef<ChatWindowRef, ChatWindowProps>(({
  messages,
  onSend,
  isStreaming,
  modelOptions,
  selectedModel,
  onModelChange,
  onCreateChat,
  onOpenToolModal,
  onToggleDeepThinking,
  deepThinkingEnabled,
  selectedDocs,
  onToggleDocMenu,
  docMenuOpen,
  onOpenFileManager,
  onOpenAddDocs,
  onRetryMessage
}, ref) => {
  const formRef = useRef<HTMLFormElement>(null);
  const transcriptRef = useRef<HTMLDivElement>(null);
  const hasUserMessage = messages.some((message) => message.role === "user");

  // Document viewer state
  const [docViewerOpen, setDocViewerOpen] = useState(false);
  const [docViewerId, setDocViewerId] = useState<string | null>(null);
  const [docViewerTitle, setDocViewerTitle] = useState("");
  const [docViewerContent, setDocViewerContent] = useState<string | null>(null);
  const [docViewerRawText, setDocViewerRawText] = useState<string | null>(null);
  const [docViewerLoading, setDocViewerLoading] = useState(false);
  const [docViewerError, setDocViewerError] = useState<string | null>(null);

  const fetchDocument = useCallback(async (documentId: string, chunkId: string | null, linkText: string) => {
    setDocViewerOpen(true);
    setDocViewerId(chunkId ? `${documentId}/${chunkId}` : documentId);
    setDocViewerTitle(linkText || "Document");
    setDocViewerContent(null);
    setDocViewerRawText(null);
    setDocViewerLoading(true);
    setDocViewerError(null);

    try {
      // If we have a chunk ID, fetch the specific chunk, otherwise fetch the full document
      const url = chunkId 
        ? `${DOCUMENT_API_BASE}/documents/${documentId}/${chunkId}`
        : `${DOCUMENT_API_BASE}/documents/${documentId}`;
      
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) {
        throw new Error(`Failed to fetch: ${res.status}`);
      }
      const data = await res.json();
      
      // Normalize text fields returned by chunk/document endpoints.
      const rawText = firstNonEmptyString(
        data?.raw_text,
        data?.original_text,
        data?.bm25_text,
        data?.text,
        data?.metadata?.raw_text,
        data?.metadata?.original_text,
        data?.metadata?.bm25_text,
        data?.metadata?.text
      );
      const content = firstNonEmptyString(
        data?.content,
        data?.document?.parsed,
        data?.parsed,
        data?.metadata?.content,
        rawText
      );
      setDocViewerContent(content);
      setDocViewerRawText(rawText);
    } catch (err) {
      setDocViewerError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setDocViewerLoading(false);
    }
  }, []);

  // Expose openDocViewer method via ref
  useImperativeHandle(ref, () => ({
    openDocViewer: (documentId: string, chunkId: string | null, title: string) => {
      fetchDocument(documentId, chunkId, title);
    }
  }), [fetchDocument]);

  const closeDocViewer = useCallback(() => {
    setDocViewerOpen(false);
    setDocViewerId(null);
    setDocViewerContent(null);
    setDocViewerRawText(null);
    setDocViewerError(null);
  }, []);

  // Custom link renderer to intercept /documents/ links and image renderer for /api/images/
  const markdownComponents: Components = {
    a: ({ href, children }) => {
      if (href && href.startsWith("/documents/")) {
        // Parse /documents/<doc_id> or /documents/<doc_id>/<chunk_id>
        const path = href.replace("/documents/", "");
        const parts = path.split("/");
        const documentId = parts[0];
        const chunkId = parts.length > 1 ? parts[1] : null;
        const linkText = typeof children === "string" ? children : String(children);
        return (
          <a
            href="#"
            onClick={(e) => {
              e.preventDefault();
              fetchDocument(documentId, chunkId, linkText);
            }}
            className="document-link"
          >
            {children}
          </a>
        );
      }
      return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
    },
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

  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const message = String(formData.get("message") ?? "").trim();

    if (!message) {
      return;
    }

    onSend(message);
    event.currentTarget.reset();
  };

  return (
    <section className="chat-pane">
      <div className="chat-header-overlay">
        <header className={`chat-header ${hasUserMessage ? "compact" : ""}`}>
          {!hasUserMessage && (
            <div className="chat-header-text">
              <h1>Hey, what do you want to work on today?</h1>
              <p className="chat-subtitle">Select your docs, arm the right tools, and start a conversation when you're ready.</p>
            </div>
          )}
        </header>

        <div className="doc-chip-row">
          {selectedDocs.length === 0 && <span className="chip muted">No docs selected</span>}
          {selectedDocs.map((doc) => (
            <span key={doc.id} className="chip">
              <span className="chip-icon-wrapper" aria-hidden="true">
                {doc.type === "folder" ? <IconFolder /> : <IconFile />}
              </span>
              {doc.name}
            </span>
          ))}
          {deepThinkingEnabled && <span className="deep-thinking-tag">Deep thinking enabled</span>}
        </div>
      </div>

      <div className="chat-transcript" ref={transcriptRef}>
        {messages.map((message) => {
          // Parse graph content for assistant messages
          const parsedContent = message.role !== "user"
            ? parseGraphContent(message.content, message.id) 
            : null;
          
          return (
            <article key={message.id} className={`chat-message ${message.role}`}>
              <header className="chat-message-meta">
                {message.role !== "assistant" && <span className="chat-role">{roleLabel[message.role]}</span>}
                <div className="chat-message-actions">
                  <time>{new Date(message.timestamp).toLocaleTimeString()}</time>
                  {message.role !== "user" && (
                    <button
                      type="button"
                      className="retry-button"
                      onClick={() => onRetryMessage(message.id)}
                      disabled={isStreaming}
                    >↻</button>
                  )}
                </div>
              </header>
              {message.role !== "user" && parsedContent ? (
                <div className="markdown-content">
                  {parsedContent.segments.map((segment, index) => {
                    if (segment.type === "graph") {
                      return (
                        <div key={segment.id} className="graph-block">
                          <GraphRenderer graphData={segment.data} id={segment.id} />
                        </div>
                      );
                    }
                    return (
                      <ReactMarkdown
                        key={`${message.id}-text-${index}`}
                        remarkPlugins={[remarkGfm]}
                        components={markdownComponents}
                      >
                        {normalizeTableSpacing(segment.content)}
                      </ReactMarkdown>
                    );
                  })}
                </div>
              ) : (
                <p>{message.content}</p>
              )}
            </article>
          );
        })}
        {isStreaming && (
          <article className="chat-message assistant loading">
            <div className="loading-lines">
              <div className="loading-line" style={{ width: "90%" }}></div>
              <div className="loading-line" style={{ width: "58%", animationDelay: "0.1s" }}></div>
              <div className="loading-line" style={{ width: "33%", animationDelay: "0.2s" }}></div>
            </div>
          </article>
        )}
      </div>
      <div className="chat-composer-container">
        <form className="chat-composer" onSubmit={handleSubmit} ref={formRef}>
          <div className="chat-input-shell">
            <textarea
              name="message"
              placeholder="Ask me anything..."
              rows={3}
              autoComplete="off"
              className="chat-input"
            />
            <div className="chat-input-footer">
              <div className="chat-input-footer-left">
                
                <div className="doc-menu-wrapper">
                  <button
                    type="button"
                    className={`chat-input-icon-button ${docMenuOpen ? "active" : ""}`}
                    onClick={onToggleDocMenu}
                    aria-label="Document options"
                  >
                    <IconPlus />
                  </button>
                  {docMenuOpen && (
                    <div className="doc-menu">
                      <button type="button" onClick={onOpenFileManager}>
                        Select where to search
                      </button>
                      <button type="button" onClick={onOpenAddDocs}>
                        Add documents
                      </button>
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  className="chat-input-icon-button"
                  onClick={onOpenToolModal}
                  aria-label="Choose tools"
                >
                  <IconGear />
                </button>
                <button
                  type="button"
                  className={`chat-input-toggle ${deepThinkingEnabled ? "active" : ""}`}
                  onClick={onToggleDeepThinking}
                  aria-label="Toggle deep thinking"
                >
                  <IconSearch />
                  {deepThinkingEnabled && <span>Deep search</span>}
                </button>
              </div>
              <div className="chat-input-footer-right">
                <div className="chat-input-model">
                  <label htmlFor="model-select">Model</label>
                  <select
                    id="model-select"
                    value={selectedModel}
                    onChange={(event) => onModelChange(event.target.value)}
                  >
                    {modelOptions.map((model) => (
                      <option key={model} value={model}>
                        {model}
                      </option>
                    ))}
                  </select>
                </div>
                <button type="submit" className="send-button" disabled={isStreaming}>
                  {isStreaming ? "…" : <IconSend />}
                </button>
              </div>
            </div>
          </div>
        </form>
      </div>

      <DocumentViewerPanel
        isOpen={docViewerOpen}
        documentId={docViewerId}
        documentTitle={docViewerTitle}
        content={docViewerContent}
        rawText={docViewerRawText}
        isLoading={docViewerLoading}
        error={docViewerError}
        onClose={closeDocViewer}
      />
    </section>
  );
});

export default ChatWindow;
