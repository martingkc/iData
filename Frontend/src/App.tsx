import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import Sidebar from "./components/Sidebar";
import ChatWindow, { ChatWindowRef } from "./components/ChatWindow";
import SettingsPanel from "./components/SettingsPanel";
import FileManagerModal from "./components/FileManagerModal";
import ToolPickerModal from "./components/ToolPickerModal";
import RemoteFilesPage from "./components/RemoteFilesPage";
import SpotlightSearch from "./components/SpotlightSearch";
import LoginPage, { UserData } from "./components/LoginPage";
import SignupPage from "./components/SignupPage";
import type { ThemeId } from "./theme";
import {
  ChatListResponse,
  ChatMessage,
  ChatMessagesResponse,
  ChatThread,
  FileNode,
  SelectedDoc,
  ToolId
} from "./types";

type AuthMode = "login" | "signup";

const availableTools: ToolId[] = [
  "retrieveDocuments",
  "summarize",
  "classify",
  "codeInterpreter"
];

const API_BASE = import.meta.env.VITE_AGENT_API_URL ?? "http://localhost:5001";

const modelOptions = ["gpt-5-mini"]; // placeholder models

const resolveInitialTheme = (): ThemeId => {
  if (typeof window === "undefined") {
    return "light";
  }
  const stored = window.localStorage.getItem("app-theme");
  if (stored === "light" || stored === "dark") {
    document.documentElement.dataset.theme = stored;
    return stored;
  }
  document.documentElement.dataset.theme = "light";
  return "light";
};

const makeId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);

const App = () => {
  const [user, setUser] = useState<UserData | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [chats, setChats] = useState<ChatThread[]>([]);
  const [activeChatId, setActiveChatId] = useState<string>("");
  const [selectedDocs, setSelectedDocs] = useState<SelectedDoc[]>([]);
  const [selectedTools, setSelectedTools] = useState<Set<ToolId>>(new Set(["retrieveDocuments"]));
  const [selectedModel, setSelectedModel] = useState(modelOptions[0]);
  const [streamingChatIds, setStreamingChatIds] = useState<Set<string>>(new Set());
  const [showSettings, setShowSettings] = useState(false);
  const [toolModalOpen, setToolModalOpen] = useState(false);
  const [deepThinkingEnabled, setDeepThinkingEnabled] = useState(false);
  const [docMenuOpen, setDocMenuOpen] = useState(false);
  const [fileManagerOpen, setFileManagerOpen] = useState(false);
  const [spotlightOpen, setSpotlightOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [fileTree, setFileTree] = useState<FileNode[]>([]);
  const [loadedMessages, setLoadedMessages] = useState<Set<string>>(new Set());
  const [activeSection, setActiveSection] = useState<"chat" | "remoteFiles" | "tasks">("chat");
  const [theme, setTheme] = useState<ThemeId>(resolveInitialTheme);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const chatWindowRef = useRef<ChatWindowRef>(null);

  // Check if user is already logged in (has valid cookie)
  useEffect(() => {
    const checkAuth = async () => {
      try {
        let res = await fetch(`${API_BASE}/auth/user`, {
          method: "POST",
          credentials: "include",
        });
        
        // If access token expired, try to refresh
        if (res.status === 401) {
          const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
            method: "POST",
            credentials: "include",
          });
          if (refreshRes.ok) {
            // Retry with new token
            res = await fetch(`${API_BASE}/auth/user`, {
              method: "POST",
              credentials: "include",
            });
          }
        }
        
        if (res.ok) {
          const userData: UserData = await res.json();
          setUser(userData);
        }
      } catch {
        // Not logged in, that's fine
      } finally {
        setAuthChecked(true);
      }
    };
    checkAuth();
  }, []);

  // Keyboard shortcut for spotlight search (Cmd+K on macOS, Ctrl+K on others)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setSpotlightOpen(true);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Auto-collapse sidebar on narrow screens
  useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 900px)");
    const handleMediaChange = (e: MediaQueryListEvent | MediaQueryList) => {
      setSidebarCollapsed(e.matches);
    };
    // Set initial state
    handleMediaChange(mediaQuery);
    // Listen for changes
    mediaQuery.addEventListener("change", handleMediaChange);
    return () => mediaQuery.removeEventListener("change", handleMediaChange);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("app-theme", theme);
  }, [theme]);

  const handleLogout = async () => {
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } catch {
      // Ignore errors
    }
    setUser(null);
    setChats([]);
    setActiveChatId("");
  };

  const activeChat = useMemo(
    () => chats.find((chat) => chat.id === activeChatId) ?? chats[0],
    [activeChatId, chats]
  );
  const isActiveChatStreaming = activeChat ? streamingChatIds.has(activeChat.id) : false;

  const selectedDocPaths = useMemo(
    () => new Set(selectedDocs.map((doc) => doc.path)),
    [selectedDocs]
  );

  const updateChat = (chatId: string, updater: (chat: ChatThread) => ChatThread) => {
    setChats((prev) =>
      prev.map((chat) => (chat.id === chatId ? updater(chat) : chat))
    );
  };

  const setChatStreaming = (chatId: string, streaming: boolean) => {
    setStreamingChatIds((prev) => {
      const next = new Set(prev);
      if (streaming) {
        next.add(chatId);
      } else {
        next.delete(chatId);
      }
      return next;
    });
  };

  // Try to refresh the access token using the refresh token cookie
  const tryRefreshToken = async (): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });
      return res.ok;
    } catch {
      return false;
    }
  };

  // Logout and redirect to login screen
  const forceLogout = () => {
    setUser(null);
    setChats([]);
    setActiveChatId("");
    setAuthMode("login");
  };

  const fetchJson = async <T,>(path: string, init?: RequestInit): Promise<T> => {
    const doFetch = async () => {
      const res = await fetch(`${API_BASE}${path}`, {
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        ...init
      });
      return res;
    };

    let res = await doFetch();

    // If unauthorized, try to refresh the token and retry once
    if (res.status === 401) {
      const refreshed = await tryRefreshToken();
      if (refreshed) {
        res = await doFetch();
      } else {
        // Refresh failed, force logout
        forceLogout();
        throw new Error("Session expired. Please log in again.");
      }
    }

    if (!res.ok) {
      // Check again for 401 after retry
      if (res.status === 401) {
        forceLogout();
        throw new Error("Session expired. Please log in again.");
      }
      const text = await res.text();
      throw new Error(text || `Request failed: ${res.status}`);
    }
    return (await res.json()) as T;
  };

  const convertTreeDictToNodes = (tree: Record<string, unknown>, basePath = ""): FileNode[] => {
    return Object.entries(tree).map(([name, value]) => {
      // Handle root "/" folder and avoid double slashes
      let path: string;
      if (name === "/") {
        path = "/";
      } else if (basePath === "/" || basePath === "") {
        path = basePath === "/" ? `/${name}` : name;
      } else {
        path = `${basePath}/${name}`;
      }
      
      if (value && typeof value === "object") {
        const children = convertTreeDictToNodes(value as Record<string, unknown>, path);
        return { id: path, name, path, type: "folder" as const, children };
      }
      return { id: path, name, path, type: "file" as const };
    });
  };

  const loadFileTree = async () => {
    try {
      const data = await fetchJson<{ files: Record<string, unknown> }>("/available_files");
      const nodes = convertTreeDictToNodes(data.files || {});
      setFileTree(nodes);
    } catch (err) {
      console.error("Failed to load file tree", err);
    }
  };

  const loadChats = async () => {
    try {
      const data = await fetchJson<ChatListResponse>("/chats");
      const mapped: ChatThread[] = data.chats.map((item) => ({
        id: item.chat_id,
        title: "Untitled chat",
        updatedAt: item.last_message?.created_at || item.created_at || new Date().toISOString(),
        messages:
          item.last_message?.content != null
            ? [
                {
                  id: `${item.chat_id}-preview`,
                  role: "assistant",
                  content: item.last_message.content,
                  timestamp: item.last_message.created_at || new Date().toISOString()
                }
              ]
            : []
      }));
      setChats(mapped);
      if (mapped.length > 0) {
        setActiveChatId(mapped[0].id);
      }
    } catch (err) {
      console.error("Failed to load chats", err);
    }
  };

  const loadMessagesForChat = async (chatId: string) => {
    if (loadedMessages.has(chatId)) return;
    try {
      const data = await fetchJson<ChatMessagesResponse>(`/chats/${chatId}/messages`);
      setChats((prev) =>
        prev.map((c) =>
          c.id === chatId
            ? {
                ...c,
                messages: data.messages.map((m, idx) => ({
                  id: `${chatId}-${idx}`,
                  role: m.role,
                  content: m.content,
                  timestamp: m.created_at
                })),
                updatedAt: data.messages[data.messages.length - 1]?.created_at || c.updatedAt,
                title:
                  c.title === "Untitled chat" && data.messages.length > 0
                    ? data.messages[0].content.slice(0, 48)
                    : c.title
              }
            : c
        )
      );
      setLoadedMessages((prev) => new Set(prev).add(chatId));
    } catch (err) {
      console.error("Failed to load messages", err);
    }
  };

  useEffect(() => {
    if (user) {
      void loadFileTree();
      void loadChats();
    }
  }, [user]);

  // Load messages when active chat changes
  useEffect(() => {
    if (activeChatId) {
      void loadMessagesForChat(activeChatId);
    }
  }, [activeChatId]);

  // Reset selected docs when switching chat sessions.
  useEffect(() => {
    setSelectedDocs([]);
  }, [activeChatId]);

  const handleCreateChat = async () => {
    try {
      setActiveSection("chat");
      setDocMenuOpen(false);
      const res = await fetchJson<{ chat_id: string }>("/chats", { method: "POST" });
      const id = res.chat_id;
      const createdAt = new Date();
      const newChat: ChatThread = {
        id,
        title: "Untitled chat",
        updatedAt: createdAt.toISOString(),
        messages: []
      };
      setChats((prev) => [newChat, ...prev]);
      setActiveChatId(id);
    } catch (err) {
      console.error("Failed to create chat", err);
    }
  };

  const handleSelectChat = (chatId: string) => {
    setActiveSection("chat");
    setActiveChatId(chatId);
    void loadMessagesForChat(chatId);
  };

  const handleDeleteChat = async (chatId: string) => {
    if (!confirm("Are you sure you want to delete this chat?")) {
      return;
    }
    try {
      await fetchJson(`/chats/${chatId}`, { method: "DELETE" });
      setChats((prev) => prev.filter((c) => c.id !== chatId));
      // If we deleted the active chat, select another one
      if (activeChatId === chatId) {
        const remaining = chats.filter((c) => c.id !== chatId);
        setActiveChatId(remaining.length > 0 ? remaining[0].id : "");
      }
    } catch (err) {
      console.error("Failed to delete chat", err);
    }
  };

  const handleToggleTool = (tool: ToolId) => {
    setSelectedTools((prev) => {
      const next = new Set(prev);
      if (next.has(tool)) {
        next.delete(tool);
      } else {
        next.add(tool);
      }
      return next;
    });
  };

  const handleSend = async (content: string) => {
    setDocMenuOpen(false);

    // If no active chat, create one first
    let chatId = activeChat?.id;
    if (!chatId) {
      try {
        const res = await fetchJson<{ chat_id: string }>("/chats", { method: "POST" });
        chatId = res.chat_id;
        const createdAt = new Date();
        const newChat: ChatThread = {
          id: chatId,
          title: "Untitled chat",
          updatedAt: createdAt.toISOString(),
          messages: []
        };
        setChats((prev) => [newChat, ...prev]);
        setActiveChatId(chatId);
      } catch (err) {
        console.error("Failed to create chat", err);
        return;
      }
    }

    const now = new Date();
    const userMessage: ChatMessage = {
      id: makeId(),
      role: "user",
      content,
      timestamp: now.toISOString()
    };

    const summary = content.length > 48 ? `${content.slice(0, 45)}…` : content;

    updateChat(chatId, (chat) => ({
      ...chat,
      title: chat.messages.length <= 1 ? summary || chat.title : chat.title,
      messages: [...chat.messages, userMessage],
      updatedAt: now.toISOString()
    }));

    setChatStreaming(chatId, true);

    try {
      // Build path_filters from selected docs/folders
      const pathFilters = selectedDocs.map((doc) => doc.path);

      const res = await fetchJson<{ chat_id: string; answer: string }>(
        `/chats/${chatId}/messages`,
        {
          method: "POST",
          body: JSON.stringify({
            text: content,
            path_filters: pathFilters,
            deep_think: deepThinkingEnabled
          })
        }
      );

      const assistantMessage: ChatMessage = {
        id: makeId(),
        role: "assistant",
        content: res.answer,
        timestamp: new Date().toISOString()
      };

      updateChat(chatId, (chat) => ({
        ...chat,
        messages: [...chat.messages, assistantMessage],
        updatedAt: assistantMessage.timestamp
      }));
    } catch (err) {
      console.error("Failed to send message", err);
    } finally {
      setChatStreaming(chatId, false);
    }
  };

  const handleFileInput = (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files) {
      return;
    }

    const nextSelection: SelectedDoc[] = Array.from(files).map((file, index) => {
      const path = file.webkitRelativePath || file.name;
      const segments = path.split("/");
      const name = segments[segments.length - 1] || path;
      return {
        id: `upload-${path}-${index}`,
        name,
        path,
        type: "file"
      };
    });

    setSelectedDocs((prev) => {
      const byPath = new Map(prev.map((doc) => [doc.path, doc]));
      nextSelection.forEach((doc) => {
        byPath.set(doc.path, doc);
      });
      return Array.from(byPath.values());
    });
    event.target.value = ""; // allow re-selecting the same folder later
  };

  const handleToggleDocMenu = () => {
    setDocMenuOpen((prev) => !prev);
  };

  const handleOpenFileManager = () => {
    setFileManagerOpen(true);
    setDocMenuOpen(false);
  };

  const handleOpenDocuments = () => {
    setFileManagerOpen(true);
    setDocMenuOpen(false);
  };

  const handleOpenAddDocs = () => {
    setDocMenuOpen(false);
    fileInputRef.current?.click();
  };

  const handleCloseFileManager = () => {
    setFileManagerOpen(false);
    setDocMenuOpen(false);
  };

  const handleToggleAppNode = (node: FileNode) => {
    setSelectedDocs((prev) => {
      const exists = prev.some((doc) => doc.path === node.path);

      if (exists) {
        return prev.filter((doc) => !doc.path.startsWith(node.path));
      }

      const entry: SelectedDoc = {
        id: `workspace-${node.path}`,
        name: node.name,
        path: node.path,
        type: node.type
      };

      const filtered = prev.filter((doc) => !doc.path.startsWith(`${node.path}/`));
      return [...filtered.filter((doc) => doc.path !== node.path), entry];
    });
  };

  const handleOpenToolModal = () => {
    setToolModalOpen(true);
    setDocMenuOpen(false);
  };

  const handleCloseToolModal = () => {
    setToolModalOpen(false);
  };

  const handleToggleDeepThinking = () => {
    setDeepThinkingEnabled((prev) => !prev);
    setDocMenuOpen(false);
  };

  const handleRetryMessage = (messageId: string) => {
    const chat = chats.find((thread) => thread.id === activeChatId);
    if (!chat) {
      return;
    }

    const targetIndex = chat.messages.findIndex((message) => message.id === messageId);
    if (targetIndex === -1) {
      return;
    }

    const targetMessage = chat.messages[targetIndex];

    if (targetMessage.role === "user") {
      handleSend(targetMessage.content);
      return;
    }

    if (targetMessage.role !== "assistant" && targetMessage.role !== "system") {
      return;
    }

    const referencePrompt = [...chat.messages.slice(0, targetIndex)]
      .reverse()
      .find((message) => message.role === "user")?.content ?? targetMessage.content;

    setChatStreaming(chat.id, true);

    setTimeout(() => {
      const refreshedMessage: ChatMessage = {
        id: makeId(),
        role: "assistant",
        content: buildAssistantStub(
          referencePrompt,
          selectedDocs,
          selectedTools,
          selectedModel,
          deepThinkingEnabled
        ),
        timestamp: new Date().toISOString()
      };

      updateChat(chat.id, (current) => {
        const idx = current.messages.findIndex((message) => message.id === messageId);
        if (idx === -1) {
          return current;
        }
        const nextMessages = [...current.messages];
        nextMessages[idx] = refreshedMessage;
        return {
          ...current,
          messages: nextMessages,
          updatedAt: refreshedMessage.timestamp
        };
      });

      setChatStreaming(chat.id, false);
    }, 650);
  };

  // Show loading while checking auth
  if (!authChecked) {
    return (
      <div className="login-container">
        <div className="login-card" style={{ textAlign: "center" }}>
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  // Show login or signup page if not authenticated
  if (!user) {
    if (authMode === "signup") {
      return (
        <SignupPage
          apiBase={API_BASE}
          onSignupSuccess={setUser}
          onSwitchToLogin={() => setAuthMode("login")}
        />
      );
    }
    return (
      <LoginPage
        apiBase={API_BASE}
        onLoginSuccess={setUser}
        onSwitchToSignup={() => setAuthMode("signup")}
      />
    );
  }

  const handleOpenRemoteFiles = () => {
    setActiveSection("remoteFiles");
    setDocMenuOpen(false);
    setFileManagerOpen(false);
    setShowSettings(false);
  };

  const handleCloseRemoteFiles = () => {
    setActiveSection("chat");
  };

  const handleOpenTasks = () => {
    setActiveSection("tasks");
    setDocMenuOpen(false);
    setFileManagerOpen(false);
    setShowSettings(false);
  };

  const handleTryTaskPrompt = async (prompt: string): Promise<string> => {
    let trialChatId: string | null = null;
    try {
      const created = await fetchJson<{ chat_id: string }>("/chats", { method: "POST" });
      trialChatId = created.chat_id;

      const trial = await fetchJson<{ chat_id: string; answer: string }>(
        `/chats/${trialChatId}/messages`,
        {
          method: "POST",
          body: JSON.stringify({
            text: prompt,
            path_filters: [],
            deep_think: false
          })
        }
      );
      return trial.answer;
    } finally {
      if (trialChatId) {
        try {
          await fetchJson(`/chats/${trialChatId}`, { method: "DELETE" });
        } catch {
          // Ignore cleanup errors for trial chat removal.
        }
      }
    }
  };

  return (
    <div className={`app-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <Sidebar
        chats={chats}
        activeChatId={activeChatId}
        activeSection={activeSection}
        onSelectChat={handleSelectChat}
        onCreateChat={handleCreateChat}
        onDeleteChat={handleDeleteChat}
        onOpenDocuments={handleOpenDocuments}
        onOpenSettings={() => setShowSettings(true)}
        onOpenSearch={() => setSpotlightOpen(true)}
        onOpenTasks={handleOpenTasks}
        user={user}
        onLogout={handleLogout}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        onOpenRemoteFiles={handleOpenRemoteFiles}
      />

      <main className="main-pane">
        {activeSection === "remoteFiles" ? (
          <RemoteFilesPage onClose={handleCloseRemoteFiles} />
        ) : activeSection === "tasks" ? (
          <TasksPage onTryPrompt={handleTryTaskPrompt} />
        ) : (
          <ChatWindow
            ref={chatWindowRef}
            messages={activeChat?.messages ?? []}
            onSend={handleSend}
            isStreaming={isActiveChatStreaming}
            modelOptions={modelOptions}
            selectedModel={selectedModel}
            onModelChange={setSelectedModel}
            onCreateChat={handleCreateChat}
            onToggleDeepThinking={() => setDeepThinkingEnabled((prev) => !prev)}
            deepThinkingEnabled={deepThinkingEnabled}
            selectedDocs={selectedDocs}
            onToggleDocMenu={handleToggleDocMenu}
            docMenuOpen={docMenuOpen}
            onOpenFileManager={handleOpenFileManager}
            onOpenAddDocs={() => fileInputRef.current?.click()}
            onRetryMessage={() => undefined}
            onOpenToolModal={handleOpenToolModal}
          />
        )}
      </main>

      <SettingsPanel
        isOpen={showSettings}
        onClose={() => setShowSettings(false)}
        theme={theme}
        onThemeChange={setTheme}
      />

      <FileManagerModal
        isOpen={fileManagerOpen}
        nodes={fileTree}
        selectedPaths={selectedDocPaths}
        onToggleNode={(node) => {
          setSelectedDocs((prev) => {
            const exists = prev.some((doc) => doc.path === node.path);
            if (exists) {
              return prev.filter((doc) => !doc.path.startsWith(node.path));
            }
            const entry: SelectedDoc = {
              id: `workspace-${node.path}`,
              name: node.name,
              path: node.path,
              type: node.type
            };
            return [...prev.filter((doc) => doc.path !== node.path), entry];
          });
        }}
        onClose={() => setFileManagerOpen(false)}
      />

      <ToolPickerModal
        isOpen={toolModalOpen}
        availableTools={availableTools}
        selectedTools={selectedTools}
        onToggleTool={handleToggleTool}
        onClose={handleCloseToolModal}
      />

      <SpotlightSearch
        isOpen={spotlightOpen}
        onClose={() => setSpotlightOpen(false)}
        onSelectResult={(documentId, chunkId, title) => {
          setSpotlightOpen(false);
          if (chatWindowRef.current) {
            chatWindowRef.current.openDocViewer(documentId, chunkId, title);
          }
        }}
      />

      <input
        type="file"
        multiple
        style={{ display: "none" }}
        ref={(node) => {
          if (node) {
            node.setAttribute("webkitdirectory", "");
            node.setAttribute("directory", "");
            node.setAttribute("mozdirectory", "");
          }
          fileInputRef.current = node;
        }}
        onChange={handleFileInput}
      />
    </div>
  );
};

const buildAssistantStub = (
  prompt: string,
  docs: SelectedDoc[],
  tools: Set<ToolId>,
  model: string,
  deepThinking: boolean
) => {
  const docList = docs.map((doc) => doc.path);
  const toolList = [...tools];

  return [
    `Model ${model} responding to: ${prompt}`,
    docList.length
      ? `- Context: ${docList.join(", ")}`
      : "- Context: no documents selected",
    toolList.length
      ? `- Tools armed: ${toolList.join(", ")}`
      : "- Tools armed: none selected",
    deepThinking ? "- Deep thinking mode enabled" : "- Deep thinking mode disabled"
  ].join("\n");
};

export default App;
