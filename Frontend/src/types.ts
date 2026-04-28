export type ToolId = "retrieveDocuments" | "summarize" | "classify" | "codeInterpreter";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
}

export interface ChatThread {
  id: string;
  title: string;
  messages: ChatMessage[];
  updatedAt: string;
}

export interface LastMessageSummary {
  content: string | null;
  created_at: string | null;
}

export interface ChatListItem {
  chat_id: string;
  thread_id: string;
  created_at: string | null;
  last_message: LastMessageSummary | null;
}

export interface ChatListResponse {
  chats: ChatListItem[];
}

export interface ChatMessagesResponse {
  chat_id: string;
  messages: { role: "user" | "assistant"; content: string; created_at: string }[];
}

export interface SelectedDoc {
  id: string;
  name: string;
  path: string;
  type: "folder" | "file";
}

export interface FileNode {
  id: string;
  name: string;
  path: string;
  type: "folder" | "file";
  children?: FileNode[];
}
