import { useState } from "react";
import { FileNode } from "../types";

interface FileManagerModalProps {
  isOpen: boolean;
  nodes: FileNode[];
  selectedPaths: Set<string>;
  onToggleNode: (node: FileNode) => void;
  onClose: () => void;
}

const IconFolder = () => (
<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path fillRule="evenodd" clipRule="evenodd" d="M4 4h8v2h10v14H2V4zm16 4H10V6H4v12h16z" fill="currentColor"/></svg>
);

const IconFile = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
  </svg>
);

const IconChevron = ({ expanded }: { expanded: boolean }) => (
  <svg 
    width="14" 
    height="14" 
    viewBox="0 0 24 24" 
    fill="none" 
    stroke="currentColor" 
    strokeWidth="2" 
    strokeLinecap="round" 
    strokeLinejoin="round"
    style={{ transform: expanded ? "rotate(90deg)" : "rotate(0deg)", transition: "transform 0.2s ease" }}
  >
    <polyline points="9 18 15 12 9 6"/>
  </svg>
);

const IconSearch = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8"/>
    <path d="m21 21-4.3-4.3"/>
  </svg>
);

const FileManagerModal = ({
  isOpen,
  nodes,
  selectedPaths,
  onToggleNode,
  onClose
}: FileManagerModalProps) => {
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");

  if (!isOpen) {
    return null;
  }

  const toggleFolder = (path: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const countSelectedInTree = (tree: FileNode[]): number => {
    let count = 0;
    for (const node of tree) {
      if (selectedPaths.has(node.path)) count++;
      if (node.children) count += countSelectedInTree(node.children);
    }
    return count;
  };

  const filterTree = (tree: FileNode[], query: string): FileNode[] => {
    if (!query.trim()) return tree;
    const lowerQuery = query.toLowerCase();
    
    const filter = (nodes: FileNode[]): FileNode[] => {
      return nodes.reduce<FileNode[]>((acc, node) => {
        const nameMatches = node.name.toLowerCase().includes(lowerQuery);
        const filteredChildren = node.children ? filter(node.children) : [];
        
        if (nameMatches || filteredChildren.length > 0) {
          acc.push({
            ...node,
            children: filteredChildren.length > 0 ? filteredChildren : node.children
          });
        }
        return acc;
      }, []);
    };
    
    return filter(tree);
  };

  const filteredNodes = filterTree(nodes, searchQuery);
  const selectedCount = countSelectedInTree(nodes);

  const renderTree = (tree: FileNode[], depth = 0): JSX.Element[] => {
    const items: JSX.Element[] = [];

    tree.forEach((node) => {
      const isChecked = selectedPaths.has(node.path);
      const isFolder = node.type === "folder";
      const isExpanded = expandedFolders.has(node.path) || searchQuery.trim() !== "";
      const hasChildren = node.children && node.children.length > 0;

      items.push(
        <div
          key={node.id}
          className={`scope-node ${isChecked ? "selected" : ""} ${node.type}`}
          style={{ paddingLeft: depth * 20 + 12 }}
        >
          {isFolder && hasChildren && (
            <button
              className="scope-node-toggle"
              onClick={() => toggleFolder(node.path)}
              aria-label={isExpanded ? "Collapse" : "Expand"}
            >
              <IconChevron expanded={isExpanded} />
            </button>
          )}
          {isFolder && !hasChildren && <span className="scope-node-toggle-spacer" />}
          <label className="scope-node-label">
            <input
              type="checkbox"
              checked={isChecked}
              onChange={() => onToggleNode(node)}
            />
            <span className="scope-node-icon">
              {isFolder ? <IconFolder /> : <IconFile />}
            </span>
            <span className="scope-node-name">{node.name}</span>
          </label>
        </div>
      );

      if (isFolder && hasChildren && isExpanded) {
        items.push(...renderTree(node.children!, depth + 1));
      }
    });

    return items;
  };

  return (
    <div className="scope-modal-overlay" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="scope-modal" onClick={(e) => e.stopPropagation()}>
        <header className="scope-modal-header">
          <div className="scope-modal-title">
            <h2>/workspace picker</h2>
            <p>Select folders and files to include when the agent searches your documents.</p>
            <div className="scope-search-bar">
              <IconSearch />
              <input
                type="text"
                placeholder="Search files and folders..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          </div>
          <button className="scope-close-button" onClick={onClose} aria-label="X">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 6 6 18M6 6l12 12"/>
            </svg>
          </button>
        </header>

        <div className="scope-tree-container">
          {filteredNodes.length > 0 ? (
            renderTree(filteredNodes)
          ) : (
            <div className="scope-empty-state">
              {searchQuery ? "No matching files or folders" : "No documents available"}
            </div>
          )}
        </div>

        <footer className="scope-modal-footer">
          <div className="scope-selection-info">
            <span className="scope-selection-count">{selectedCount}</span>
            <span>{selectedCount === 1 ? "item" : "items"} selected</span>
          </div>
          <button className="scope-done-button" onClick={onClose}>
            Done
          </button>
        </footer>
      </div>
    </div>
  );
};

export default FileManagerModal;
