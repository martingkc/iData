import { ToolId } from "../types";

const TOOL_LABELS: Record<ToolId, string> = {
  retrieveDocuments: "Retriever",
  summarize: "Summarizer",
  classify: "Classifier",
  codeInterpreter: "Code Interpreter"
};

interface ToolPickerProps {
  availableTools: ToolId[];
  selectedTools: Set<ToolId>;
  onToggleTool: (tool: ToolId) => void;
}

const ToolPicker = ({ availableTools, selectedTools, onToggleTool }: ToolPickerProps) => (
  <div className="tool-picker">
    <h3>Tools</h3>
    <p className="tool-picker-hint">Enable the helpers the agent may call.</p>
    <div className="tool-grid">
      {availableTools.map((tool) => {
        const isActive = selectedTools.has(tool);
        return (
          <button
            key={tool}
            className={`tool-chip ${isActive ? "active" : ""}`}
            onClick={() => onToggleTool(tool)}
            type="button"
          >
            {TOOL_LABELS[tool]}
          </button>
        );
      })}
    </div>
  </div>
);

export default ToolPicker;
