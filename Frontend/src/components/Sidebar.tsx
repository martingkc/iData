import { useMemo, type ReactNode } from "react";
import { ChatThread } from "../types";

interface UserData {
  email: string;
  name: string;
  surname: string;
}

interface SidebarProps {
  chats: ChatThread[];
  activeChatId: string;
  onSelectChat: (chatId: string) => void;
  onCreateChat: () => void;
  onDeleteChat: (chatId: string) => void;
  onOpenDocuments: () => void;
  onOpenSettings: () => void;
  onOpenSearch: () => void;
  user?: UserData | null;
  onLogout?: () => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onOpenRemoteFiles?: () => void;
}

interface QuickAction {
  label: string;
  icon?: string;
  iconNode?: ReactNode;
  action: () => void;
}

const IconFolder = () => (
<svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M3.333 3.333H10V5h8.333v11.667H1.667V3.333zm13.333 3.333H8.333V5h-5v10h13.333z" fill="currentColor"/></svg>
);

const IconCloud = () => (
<svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M13.333 3.333h-5V5H6.667v1.667H3.333v1.667H1.667v1.667H0v5h1.667v1.667h16.667v-1.667h1.667v-5h-1.667V8.334h-1.667V6.667H15V5h-1.667zM15 10h3.333v5H1.667v-5h1.667V8.333h3.333V10h1.667V8.333H6.667V6.667h1.667V5h5v1.667h1.667zm0 0v1.667h-1.667V10z" fill="currentColor"/></svg>
);

const IconTrash = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path
      fillRule="evenodd"
      clipRule="evenodd"
      d="M14 0H14.0002V2H14V4H16H18H20V6H18V18H18.0002V20L18 20H16H4.00024L2.00024 20V18V6H0V4H2.00024H4.00024H6.00024V2V0H8.00024H12H14ZM12 2H8.00024V4H12V2ZM12 6H8.00024H6.00024L4.00024 6V18H16V6L14 6H12ZM7 8H9V16H7V8ZM13.0002 8H11.0002V16H13.0002V8Z"
      fill="currentColor"
    />
  </svg>
);

const IconSearch = () => (
<svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" clip-rule="evenodd" d="M5 1.667h6.667v1.667H5zM3.333 5V3.333h1.667v1.667zm0 6.667H1.667V5h1.667zm1.667 1.667H3.333v-1.667h1.667zm6.667 0v1.667H5v-1.667zm1.667 -1.667h-1.667v1.667h1.667v1.667h1.667v1.667h1.667v1.667h1.667v-1.667h-1.667v-1.667h-1.667v-1.667h-1.667zm0 -6.667h1.667v6.667h-1.667zm0 0V3.333h-1.667v1.667z" fill="currentColor"/></svg>
);

const IconGear = () => (
  <svg xmlns="http://www.w3.org/2000/svg" version="1.1" height="20" width="20" viewBox="3.6645970344543457 3.680098295211792 92.3938980102539 92.3938980102539"><path d="m43.266 92.754v-3.3008h-6.6016v-6.6016h-6.6016v6.6016h-13.195v-6.6016h-6.6016v-13.195h6.6016v-6.6016h-6.6016v-6.6016h-6.6016v-13.195h6.6016v-6.6016h6.6016v-6.6016h-6.6016l0.007813-6.582v-6.5977h6.6016v-6.5977h13.195v6.6016h6.6016l-0.003906-3.3047v-3.2969h6.6016l-0.003906-3.3008v-3.2969h13.195v6.6016h6.6016v6.6016h6.6016l-0.003906-3.3086v-3.2969h13.195v6.6016h6.6016v13.195h-6.6016v6.6016h6.6016v6.6016h6.6016v13.195h-6.6016v6.6016h-6.6016v6.6016h6.6016v13.195h-6.6016v6.6016h-13.195v-6.6016h-6.6016v6.6016h-6.6016v6.6016h-13.195zm13.195-9.8984v-6.5977h13.195v6.6016h13.195v-13.195h-6.6016v-13.195h13.195v-13.195h-13.195v-13.195h6.6016l0.003907-6.6055v-6.5977h-13.195v6.6016h-13.195v-13.199h-13.195v13.195h-13.195l-0.003907-3.2969v-3.3008h-13.195v13.195h6.6016v13.195h-13.195v13.195h13.195v13.195h-6.6016v13.195h13.195v-6.6016h13.195v13.195h13.195zm-13.195-16.496v-3.3008h-6.6016v-6.6016h-6.6016v-13.195h6.6016v-6.6016h6.6016v-6.6016h13.195v6.6016h6.6016v6.6016h6.6016v13.195h-6.6016v6.6016h-6.6016v6.6016h-13.195zm13.195-6.5977v-3.3008h6.6016v-13.195h-6.6016v-6.6016h-13.195v6.6016h-6.6016v13.195h6.6016v6.6016h13.195z" fill="currentColor"/></svg>
);

const Sidebar = ({
  chats,
  activeChatId,
  onSelectChat,
  onCreateChat,
  onDeleteChat,
  onOpenDocuments,
  onOpenSettings,
  onOpenSearch,
  user,
  onLogout,
  collapsed = false,
  onToggleCollapse,
  onOpenRemoteFiles
}: SidebarProps) => {
  const sortedChats = useMemo(
    () => [...chats].sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1)),
    [chats]
  );

  const quickActions: QuickAction[] = [
    {
      label: "New Chat",
      icon: "fa-solid fa-plus",
      action: onCreateChat
    },
    {
      label: "Search",
      iconNode: <IconSearch />,
      action: onOpenSearch
    },
    {
      label: "Workspace",
      iconNode: <IconFolder />,
      action: onOpenDocuments
    },
    ...(onOpenRemoteFiles
      ? [
          {
            label: "Remote Files",
            iconNode: <IconCloud />,
            action: onOpenRemoteFiles
          }
        ]
      : []),
    {
      label: "Settings",
      iconNode: <IconGear />,
      action: onOpenSettings
    }
  ];

  return (
    <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
      <button 
        className="sidebar-toggle" 
        onClick={onToggleCollapse}
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        <i className={`fa-solid ${collapsed ? "fa-angles-right" : "fa-angles-left"}`} aria-hidden="true" />
      </button>
      {!collapsed && (
        <div className="sidebar-brand">
          <div className="sidebar-logo-box">
            <span className="sidebar-logo-text">data/cow</span>
          </div>
        </div>
      )}
      <nav className="sidebar-nav" aria-label="Primary">
        {quickActions.map((item) => (
          <button key={item.label} className="sidebar-nav-button" onClick={item.action} title={item.label}>
            {item.iconNode ? (
              <span className="sidebar-nav-icon" aria-hidden="true">
                {item.iconNode}
              </span>
            ) : (
              <i className={`sidebar-nav-icon ${item.icon ?? ""}`} aria-hidden="true" />
            )}
            {!collapsed && <span>{item.label}</span>}
          </button>
        ))}
      </nav>

      {!collapsed && (
        <div className="sidebar-section">
          <header className="sidebar-header">
            <h2>/sessions</h2>
          </header>
          <div className="chat-list">
            {sortedChats.map((chat) => {
              const isActive = chat.id === activeChatId;
              return (
                <div key={chat.id} className={`chat-list-item ${isActive ? "active" : ""}`}>
                  <button
                    className="chat-list-item-content"
                    onClick={() => onSelectChat(chat.id)}
                  >
                    <span className="chat-title">{chat.title}</span>
                    <span className="chat-updated">{new Date(chat.updatedAt).toLocaleString()}</span>
                  </button>
                  <button
                    className="chat-delete-button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteChat(chat.id);
                    }}
                  title="Delete chat"
                >
                  <IconTrash />
                </button>
              </div>
            );
          })}
          {sortedChats.length === 0 && <p className="empty-state">No conversations yet.</p>}
        </div>
      </div>
      )}

      {user && (
        <div className="sidebar-user">
          {!collapsed && (
            <div className="user-info">
              <span className="user-name">{user.name} {user.surname}</span>
              <span className="user-email">{user.email}</span>
            </div>
          )}
          {onLogout && (
            <button className="logout-button" onClick={onLogout} title="Sign out">
              <i className="fa-solid fa-right-from-bracket" aria-hidden="true" />
            </button>
          )}
        </div>
      )}
    </aside>
  );
};

export default Sidebar;
