import { ToolId } from "../types";
import ToolPicker from "./ToolPicker";

interface ToolPickerModalProps {
  isOpen: boolean;
  availableTools: ToolId[];
  selectedTools: Set<ToolId>;
  onToggleTool: (tool: ToolId) => void;
  onClose: () => void;
}

const ToolPickerModal = ({
  isOpen,
  availableTools,
  selectedTools,
  onToggleTool,
  onClose
}: ToolPickerModalProps) => {
  if (!isOpen) {
    return null;
  }

  return (
    <div className="tool-modal-overlay" role="dialog" aria-modal="true">
      <div className="tool-modal-panel">
        <header className="tool-modal-header">
          <div>
            <h2>Agent Tools</h2>
            <p>Toggle the helpers the assistant can invoke during this chat.</p>
          </div>
          <button className="ghost-button" onClick={onClose}>
            Close
          </button>
        </header>
        <ToolPicker
          availableTools={availableTools}
          selectedTools={selectedTools}
          onToggleTool={onToggleTool}
        />
      </div>
    </div>
  );
};

export default ToolPickerModal;
