import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { SimpleTreeView } from "@mui/x-tree-view/SimpleTreeView";
import { TreeItem } from "@mui/x-tree-view/TreeItem";

const DOCUMENT_COLLECTOR_API_BASE = import.meta.env.VITE_DOCUMENT_COLLECTOR_API_URL ?? "http://localhost:8001";
const USER_RCLONE_API_BASE = import.meta.env.VITE_USER_RCLONE_API_URL ?? "http://localhost:13000";

type RemoteType = "drive" | "local";

type RemoteEntry = {
  name: string;
};



type RemoteContentEntry = {
  Path?: string;
  Name?: string;
  IsDir?: boolean;
  Size?: number;
  MimeType?: string;
  ModTime?: string;
};

type RemoteContentResponse = {
  // keeping this flexible; rclone wrappers vary
  list?: RemoteContentEntry[];
  entries?: RemoteContentEntry[];
  files?: RemoteContentEntry[];
  dirs?: RemoteContentEntry[];
  items?: RemoteContentEntry[];
  [key: string]: unknown;
};

type RemoteNode = {
  id: string;
  name: string;
  path: string;
  type: "folder" | "file";
  children?: RemoteNode[];
  loaded?: boolean;
};

type TreeNode = {
  id: number;
  name: string;
  children: number[];
  parent: number | null;
  isBranch?: boolean;
  metadata?: {
    remote: string;
    path: string;
    type: "folder" | "file";
  };
};

const normalizeToArray = (data: RemoteContentResponse): RemoteContentEntry[] => {
  const candidates = [data.list, data.entries, data.items, data.dirs, data.files];
  for (const c of candidates) {
    if (Array.isArray(c)) return c;
  }
  // Some backends just return an array
  if (Array.isArray(data as unknown)) return data as unknown as RemoteContentEntry[];
  return [];
};

const joinRemotePath = (base: string, name: string) => {
  if (!base || base === "/") return `/${name}`;
  return `${base.replace(/\/$/, "")}/${name}`;
};

const IconCloud = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path
      fillRule="evenodd"
      clipRule="evenodd"
      d="M16 4H10V6H8V8H4V10H2V12H0V18H2V20H22V18H24V12H22V10H20V8H18V6H16V4ZM18 12H20H22V18H2V12H4V10H8V12H10V10H8V8H10V6H16V8H18V10V12ZM18 12V14H16V12H18Z"
      fill="black"
    />
  </svg>
);

const IconChevron = ({ expanded }: { expanded: boolean }) => (
  <svg className={`scope-chevron ${expanded ? "expanded" : ""}`} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="m9 18 6-6-6-6" />
  </svg>
);

const IconFolder = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path
      fillRule="evenodd"
      clipRule="evenodd"
      d="M4 4H12V6H20H22V8L22 18V20L20 20H4L2 20V18V6V4H4ZM20 8H10V6H4V18H20V8Z"
      fill="black"
    />
  </svg>
);

const IconFile = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <path d="M14 2v6h6" />
  </svg>
);

const RemoteFilesPage = ({ onClose }: { onClose?: () => void }) => {
  const [remotes, setRemotes] = useState<RemoteEntry[]>([]);
  const [loadingRemotes, setLoadingRemotes] = useState(false);
  const [errorRemotes, setErrorRemotes] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [newRemoteName, setNewRemoteName] = useState("");
  const [newRemoteType, setNewRemoteType] = useState<RemoteType>("drive");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [activeRemote, setActiveRemote] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [treeData, setTreeData] = useState<TreeNode[]>([]);
  const [expandedIds, setExpandedIds] = useState<number[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [searchQuery, setSearchQuery] = useState("");

  // MUI TreeView expects string ids
  const expandedItems = useMemo(() => expandedIds.map(String), [expandedIds]);
  const selectedItems = useMemo(() => selectedIds.map(String), [selectedIds]);

  // Track which nodes are currently fetching children (used for spinners / disabling repeated expand)
  const [loadingNodes, setLoadingNodes] = useState<Set<string>>(new Set());

  const nodeById = useMemo(() => new Map(treeData.map((n) => [n.id, n])), [treeData]);

  const getDescendantIds = useCallback(
    (startId: number) => {
      const out: number[] = [];
      const stack: number[] = [...(nodeById.get(startId)?.children ?? [])];
      const seen = new Set<number>();
      while (stack.length) {
        const id = stack.pop()!;
        if (seen.has(id)) continue;
        seen.add(id);
        out.push(id);
        const n = nodeById.get(id);
        if (n?.children?.length) stack.push(...n.children);
      }
      return out;
    },
    [nodeById]
  );

  const getAncestorIds = useCallback(
    (startId: number) => {
      const out: number[] = [];
      let cur = nodeById.get(startId);
      const seen = new Set<number>();
      while (cur && cur.parent != null) {
        const pid = cur.parent;
        if (seen.has(pid)) break;
        seen.add(pid);
        out.push(pid);
        cur = nodeById.get(pid);
      }
      return out;
    },
    [nodeById]
  );

  // Only send top-level selected paths (if a parent is selected, do not include its descendants)
  const topLevelSelectedIds = useMemo(() => {
    const selected = new Set(selectedIds);
    const top: number[] = [];
    for (const id of selectedIds) {
      const ancestors = getAncestorIds(id);
      if (ancestors.some((a) => selected.has(a))) continue;
      top.push(id);
    }
    return top;
  }, [getAncestorIds, selectedIds]);

  const selectedPathsCount = topLevelSelectedIds.length;

  useEffect(() => {
    const next = new Set<string>();
    for (const id of topLevelSelectedIds) {
      const node = nodeById.get(id);
      const p = node?.metadata?.path;
      if (p) next.add(p);
    }
    setSelectedPaths(next);
  }, [nodeById, topLevelSelectedIds]);

  // Stable mapping so ids never collide and don't change across expansions
  const nodeIdByKey = useRef<Map<string, number>>(new Map());
  const nextNodeId = useRef(1);
  const getNodeId = useCallback((remote: string, path: string) => {
    const key = `${remote}::${path}`;
    const existing = nodeIdByKey.current.get(key);
    if (existing != null) return existing;
    const id = nextNodeId.current++;
    nodeIdByKey.current.set(key, id);
    return id;
  }, []);

  // Prevent concurrent duplicate expands of the same node.
  const expandInFlight = useRef<Set<number>>(new Set());

  // First occurrence wins: dedupe entries by their computed full path under the current parent.
  const dedupeEntriesByChildPath = useCallback((parentPath: string, entries: RemoteContentEntry[]) => {
    const seen = new Set<string>();
    const out: RemoteContentEntry[] = [];
    for (const e of entries) {
      const name = e.Name ?? e.Path?.split("/").filter(Boolean).pop() ?? "";
      if (!name) continue;
      const childPath = joinRemotePath(parentPath, name);
      if (seen.has(childPath)) continue;
      seen.add(childPath);
      out.push(e);
    }
    return out;
  }, []);

  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState<string | null>(null);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast(null), 2200);
  }, []);

  const fetchRemotes = useCallback(async () => {
    setLoadingRemotes(true);
    setErrorRemotes(null);
    try {
      const res = await fetch(`${DOCUMENT_COLLECTOR_API_BASE}/rclone/list_remotes`, {
        credentials: "include"
      });
      if (!res.ok) {
        throw new Error(`Failed: ${res.status}`);
      }
      const data = (await res.json()) as unknown;
      const names = Array.isArray(data) ? (data as string[]) : [];
      setRemotes(names.map((name) => ({ name })));
    } catch (err) {
      setErrorRemotes(err instanceof Error ? err.message : "Failed to load remotes");
      setRemotes([]);
    } finally {
      setLoadingRemotes(false);
    }
  }, []);

  useEffect(() => {
    void fetchRemotes();
  }, [fetchRemotes]);

  const listRemoteContents = useCallback(
    async (remoteName: string, path: string) => {
      const res = await fetch(`${DOCUMENT_COLLECTOR_API_BASE}/rclone/list_remote_contents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          remote_name: remoteName,
          path,
          max_depth: 1,
          dirs_only: false,
          files_only: false
        })
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Failed: ${res.status}`);
      }
      const data = (await res.json()) as RemoteContentResponse;
      return normalizeToArray(data);
    },
    []
  );

  const setNodeLoading = (nodeId: string, isLoading: boolean) => {
    setLoadingNodes((prev) => {
      const next = new Set(prev);
      if (isLoading) next.add(nodeId);
      else next.delete(nodeId);
      return next;
    });
  };

  const refreshRemoteTreeRoot = useCallback(
    async (remoteName: string) => {
      // Reset id maps between remotes so tree is clean and deterministic
      nodeIdByKey.current = new Map();
      nextNodeId.current = 1;

      const rootPath = "/";
      const rootId = getNodeId(remoteName, rootPath);

      setNodeLoading(String(rootId), true);
      try {
        const entriesRaw = await listRemoteContents(remoteName, rootPath);
        const entries = dedupeEntriesByChildPath(rootPath, entriesRaw);

        const childNodes: TreeNode[] = entries
          .map((e) => {
            const name = e.Name ?? e.Path?.split("/").filter(Boolean).pop() ?? "";
            if (!name) return null;

            const isDir = Boolean(e.IsDir);
            const path = joinRemotePath(rootPath, name);
            const id = getNodeId(remoteName, path);

            return {
              id,
              name,
              children: [],
              parent: rootId,
              isBranch: isDir,
              metadata: { remote: remoteName, path, type: isDir ? "folder" : "file" }
            } satisfies TreeNode;
          })
          .filter(Boolean) as TreeNode[];

        childNodes.sort((a, b) => {
          const at = a.metadata?.type;
          const bt = b.metadata?.type;
          if (at !== bt) return at === "folder" ? -1 : 1;
          return a.name.localeCompare(b.name);
        });

        const root: TreeNode = {
          id: rootId,
          name: "",
          children: childNodes.map((c) => c.id),
          parent: null,
          isBranch: true,
          metadata: { remote: remoteName, path: rootPath, type: "folder" }
        };

        setTreeData([root, ...childNodes]);
        setExpandedIds([rootId]);
        setSelectedIds([]);
        setSelectedPaths(new Set());
        setSearchQuery("");
      } finally {
        setNodeLoading(String(rootId), false);
      }
    },
    [dedupeEntriesByChildPath, getNodeId, listRemoteContents]
  );

  const handleSelectRemote = useCallback(
    async (remoteName: string) => {
      setActiveRemote(remoteName);
      try {
        await refreshRemoteTreeRoot(remoteName);
      } catch (err) {
        showToast(err instanceof Error ? err.message : "Failed to load remote content");
        setTreeData([]);
      }
    },
    [refreshRemoteTreeRoot, showToast]
  );

  const addOrUpdateChildren = (parentId: number, children: TreeNode[]) => {
    setTreeData((prev) => {
      const byId = new Map(prev.map((n) => [n.id, n]));
      const parent = byId.get(parentId);
      if (!parent) return prev;

      for (const child of children) {
        byId.set(child.id, child);
      }

      const sortedChildIds = [...children]
        .sort((a, b) => {
          const at = a.metadata?.type;
          const bt = b.metadata?.type;
          if (at !== bt) return at === "folder" ? -1 : 1;
          return a.name.localeCompare(b.name);
        })
        .map((c) => c.id);

      byId.set(parentId, { ...parent, children: sortedChildIds, isBranch: true });
      return Array.from(byId.values());
    });
  };

  const handleExpand = useCallback(
    async ({ element, isExpanded }: { element: TreeNode; isExpanded: boolean }) => {
      setExpandedIds((prev) => {
        const next = new Set(prev);
        if (isExpanded) next.add(element.id);
        else next.delete(element.id);
        return Array.from(next);
      });

      if (!isExpanded) return;
      if (!activeRemote) return;
      if (!element.isBranch) return;
      if (element.children.length > 0) return;
      if (expandInFlight.current.has(element.id)) return;

      const path = element.metadata?.path;
      if (!path) return;

      expandInFlight.current.add(element.id);
      setNodeLoading(String(element.id), true);
      try {
        const entriesRaw = await listRemoteContents(activeRemote, path);
        const entries = dedupeEntriesByChildPath(path, entriesRaw);

        const children: TreeNode[] = entries
          .map((e) => {
            const name = e.Name ?? e.Path?.split("/").filter(Boolean).pop() ?? "";
            if (!name) return null;

            const isDir = Boolean(e.IsDir);
            const childPath = joinRemotePath(path, name);
            const id = getNodeId(activeRemote, childPath);

            return {
              id,
              name,
              children: [],
              parent: element.id,
              isBranch: isDir,
              metadata: { remote: activeRemote, path: childPath, type: isDir ? "folder" : "file" }
            } satisfies TreeNode;
          })
          .filter(Boolean) as TreeNode[];

        addOrUpdateChildren(element.id, children);
      } catch (err) {
        showToast(err instanceof Error ? err.message : "Failed to load folder");
      } finally {
        setNodeLoading(String(element.id), false);
        expandInFlight.current.delete(element.id);
      }
    },
    [activeRemote, dedupeEntriesByChildPath, getNodeId, listRemoteContents, showToast]
  );

  // Helper to render a subtree using MUI TreeItem.
  const renderTree = (nodeId: number): JSX.Element | null => {
    const node = nodeById.get(nodeId);
    if (!node) return null;

    const meta = node.metadata;
    const isFolder = meta?.type === "folder";
    const isLoading = loadingNodes.has(String(node.id));
    const isExpanded = expandedIds.includes(node.id);

    const isSelected = selectedIds.includes(node.id);

    const handleCheckboxToggle = (checked: boolean) => {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        const descendants = getDescendantIds(node.id);

        if (checked) {
          next.add(node.id);
          for (const d of descendants) next.add(d);
        } else {
          next.delete(node.id);
          for (const d of descendants) next.delete(d);
        }

        return Array.from(next);
      });
    };

    const toggleExpand = async () => {
      if (!node.isBranch) return;
      const willExpand = !expandedIds.includes(node.id);

      // Keep UI expanded state in sync
      setExpandedIds((prev) => {
        const next = new Set(prev);
        if (willExpand) next.add(node.id);
        else next.delete(node.id);
        return Array.from(next);
      });

      // Lazy-load children only when expanding
      if (willExpand) {
        await handleExpand({ element: node, isExpanded: true });
      }
    };

    return (
      <TreeItem
        key={node.id}
        itemId={String(node.id)}
        label={
          <div className={`scope-node ${isSelected ? "selected" : ""} ${isFolder ? "folder" : "file"}`}
            style={{ paddingLeft: 0 }}
          >
            {node.isBranch ? (
              <button
                type="button"
                className="scope-node-toggle"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  void toggleExpand();
                }}
                aria-label={isExpanded ? "Collapse" : "Expand"}
              >
                <IconChevron expanded={Boolean(isExpanded)} />
              </button>
            ) : (
              <span className="scope-node-toggle-spacer" />
            )}

            <label className="scope-node-label" onClick={(e) => e.stopPropagation()}>
              <input type="checkbox" checked={isSelected} onChange={(e) => handleCheckboxToggle(e.target.checked)} />
              <span className="scope-node-icon">{isFolder ? <IconFolder /> : <IconFile />}</span>
              <span className="scope-node-name">{node.name || (meta?.path === "/" ? "/" : "")}</span>
            </label>

            {isLoading && <span className="scope-node-meta">loading</span>}
          </div>
        }
        onClick={(e) => {
          // Row click toggles selection only (no expand)
          e.preventDefault();
          e.stopPropagation();
          handleCheckboxToggle(!isSelected);
        }}
      >
        {node.children.map((cid) => renderTree(cid))}
      </TreeItem>
    );
  };

  const filteredTreeData = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return treeData;

    const keep = new Set<number>();
    const root = treeData.find((n) => n.parent === null);
    if (root) keep.add(root.id);

    const byId = new Map(treeData.map((n) => [n.id, n]));

    for (const n of treeData) {
      if (!n.name) continue;
      if (n.name.toLowerCase().includes(q)) {
        let cur: TreeNode | undefined = n;
        while (cur) {
          keep.add(cur.id);
          cur = cur.parent != null ? byId.get(cur.parent) : undefined;
        }
      }
    }

    const keptNodes = treeData.filter((n) => keep.has(n.id));
    const keptIds = new Set(keptNodes.map((n) => n.id));
    return keptNodes.map((n) => ({ ...n, children: n.children.filter((cid) => keptIds.has(cid)) }));
  }, [searchQuery, treeData]);

  const handleCreateRemote = async () => {
    setCreating(true);
    setCreateError(null);
    try {
      const name = newRemoteName.trim();
      if (!name) throw new Error("Remote name is required");

      // 1) Get a headless config token from the document collector authorize endpoint
      console.log("Requesting config token for remote type:", newRemoteType);
      console.log(`Calling authorize endpoint : ${USER_RCLONE_API_BASE}/rclone/authorize_rclone_remote?remote_type=${encodeURIComponent(newRemoteType)}`);
      const tokenRes = await fetch(`${USER_RCLONE_API_BASE}/rclone/authorize_rclone_remote?remote_type=${encodeURIComponent(newRemoteType)}`, {
        method: "POST",
        credentials: "include"
      });
      console.log("Received token response:", tokenRes);
      if (!tokenRes.ok) {
        const text = await tokenRes.text();
        throw new Error(text || `Failed to get token: ${tokenRes.status}`);
      }
      console.log("Parsing token response JSON");
      const tokenData = (await tokenRes.json()) as any;
      const configToken: string | undefined = tokenData?.token;
      if (!configToken || typeof configToken !== "string") {
        throw new Error("Authorize endpoint did not return a token");
      }
      console.log("Received config token:", configToken);
      // 2) Call document collector with schema-compatible body (RcloneRemoteCreateRequest)
      const res = await fetch(`${DOCUMENT_COLLECTOR_API_BASE}/rclone/configure_headless_remote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          name,
          type: newRemoteType,
          config_token: configToken
        })
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Failed: ${res.status}`);
      }
      setCreateOpen(false);
      setNewRemoteName("");
      setNewRemoteType("drive");
      showToast("Remote configuration started.");
      await fetchRemotes();
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Failed to create remote");
    } finally {
      setCreating(false);
    }
  };

  const syncPlaceholder = async () => {
    if (!activeRemote) {
      showToast("Select a remote first.");
      return;
    }
    if (selectedPaths.size === 0) {
      showToast("Select files/folders to sync.");
      return;
    }

    try {
      const payload = {
        requests: Array.from(selectedPaths).map((source_path) => ({
          remote_name: activeRemote,
          source_path,
          schedule_periodical_sync: false
        }))
      };

      const res = await fetch(`${DOCUMENT_COLLECTOR_API_BASE}/rclone/sync_paths`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Failed: ${res.status}`);
      }

      showToast(`Sync queued: ${selectedPaths.size} item(s).`);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Sync failed");
    }
  };

  const remoteNames = useMemo(() => remotes.map((r) => r.name), [remotes]);

  return (
    <div className="remote-files-page">
      <header className="remote-files-header">
        <div>
          <h1>Remote Files</h1>
          <p className="remote-files-subtitle">Browse configured rclone remotes via the document collector API.</p>
        </div>
        <div className="remote-files-actions">
          <button className="ghost-button" onClick={() => setCreateOpen(true)} type="button">
            Create a new remote
          </button>
          {onClose && (
            <button className="ghost-button" onClick={onClose} type="button">
              Close
            </button>
          )}
        </div>
      </header>

      <section className="remote-files-grid">
        <aside className="remote-files-panel">
          <div className="remote-files-panel-header">
            <h2>Remotes</h2>
            <button className="ghost-button" onClick={() => void fetchRemotes()} type="button" disabled={loadingRemotes}>
              Refresh
            </button>
          </div>
          {errorRemotes && <div className="login-error">{errorRemotes}</div>}
          <div className="remote-list">
            {loadingRemotes && <p className="empty-state">Loading</p>}
            {!loadingRemotes && remoteNames.length === 0 && <p className="empty-state">No remotes configured.</p>}
            {remoteNames.map((name) => (
              <button
                key={name}
                className={`remote-list-item ${activeRemote === name ? "active" : ""}`}
                onClick={() => void handleSelectRemote(name)}
                type="button"
              >
                <span className="remote-list-icon">
                  <IconCloud />
                </span>
                <span className="remote-list-name">{name}</span>
              </button>
            ))}
          </div>
        </aside>

        <section className="remote-files-panel">
          <div className="remote-files-panel-header">
            <h2>{activeRemote ? `Contents: ${activeRemote}` : "Contents"}</h2>
            <div className="remote-files-sync">
              <span className="remote-files-selection">Selected: {selectedPathsCount}</span>
              <button className="ghost-button" onClick={syncPlaceholder} type="button">
                Sync
              </button>
            </div>
          </div>

          {!activeRemote && <p className="empty-state">Select a remote to browse its files.</p>}

          {activeRemote && (
            <>
              <div className="remote-tree-toolbar">
                <input
                  className="remote-tree-search"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search remote files"
                />
                <button
                  className="ghost-button"
                  onClick={() => {
                    setSearchQuery("");
                    setExpandedIds((prev) => (prev.length ? prev : prev));
                  }}
                  type="button"
                >
                  Clear
                </button>
              </div>

              <div className="remote-tree remote-tree-scroll">
                {treeData.length === 0 ? (
                  <p className="empty-state">No data.</p>
                ) : (
                  <SimpleTreeView
                    className="remote-mui-tree"
                    multiSelect
                    expandedItems={expandedItems}
                    selectedItems={selectedItems}
                    onExpandedItemsChange={(_, itemIds) => {
                      const next = (itemIds ?? []).map((s) => Number(s)).filter((n) => Number.isFinite(n));
                      setExpandedIds(next);
                    }}
                    // Selection is handled by our custom checkboxes; keep MUI selection in sync only.
                    onSelectedItemsChange={() => {}}
                  >
                    {(() => {
                      const root = filteredTreeData.find((n) => n.parent === null);
                      if (!root) return null;
                      // Render root's children (hide the synthetic empty root label)
                      return root.children.map((cid) => renderTree(cid));
                    })()}
                  </SimpleTreeView>
                )}
              </div>
            </>
          )}
        </section>
      </section>

      {createOpen && (
        <div className="scope-modal-overlay" role="dialog" aria-modal="true" onClick={() => setCreateOpen(false)}>
          <div
            className="scope-modal"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: "var(--modal-max-width)", width: "var(--modal-width)" }}
          >
            <header className="scope-modal-header">
              <div className="scope-modal-title">
                <h2>Create remote</h2>
                <p>Create a new rclone remote (headless flow).</p>
              </div>
              <button className="ghost-button" onClick={() => setCreateOpen(false)} type="button">
                Close
              </button>
            </header>

            <div className="settings-section" style={{ marginTop: 0, padding: "var(--modal-padding)" }}>
              {createError && <div className="login-error">{createError}</div>}

              <label className="settings-field">
                <span>Name</span>
                <input value={newRemoteName} onChange={(e) => setNewRemoteName(e.target.value)} placeholder="my-remote" />
              </label>

              <label className="settings-field">
                <span>Remote type</span>
                <select value={newRemoteType} onChange={(e) => setNewRemoteType(e.target.value as RemoteType)}>
                  <option value="drive">drive</option>
                  <option value="local">local</option>
                </select>
              </label>

              <div style={{ display: "flex", gap: ".75rem", justifyContent: "flex-end", marginTop: "1rem" }}>
                <button className="ghost-button" onClick={() => setCreateOpen(false)} type="button">
                  Cancel
                </button>
                <button
                  className="ghost-button"
                  onClick={() => void handleCreateRemote()}
                  type="button"
                  disabled={creating || !newRemoteName.trim()}
                >
                  {creating ? "Creating" : "Create"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {toast && <div className="remote-toast">{toast}</div>}
    </div>
  );
};

export default RemoteFilesPage;
