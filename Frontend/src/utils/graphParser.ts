import { GraphData } from "../components/GraphRenderer";

export interface ParsedContent {
  segments: ContentSegment[];
}

export type ContentSegment =
  | { type: "text"; content: string }
  | { type: "graph"; data: GraphData; id: string };

/**
 * Parses message content to extract <graph>...</graph> blocks.
 * Returns an array of segments that are either text or graph data.
 */
export function parseGraphContent(content: string, messageId: string): ParsedContent {
  const segments: ContentSegment[] = [];
  const graphRegex = /<graph>([\s\S]*?)<\/graph>/gi;
  
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let graphIndex = 0;

  while ((match = graphRegex.exec(content)) !== null) {
    // Add text before this graph block
    if (match.index > lastIndex) {
      const textContent = content.slice(lastIndex, match.index).trim();
      if (textContent) {
        segments.push({ type: "text", content: textContent });
      }
    }

    // Try to parse the graph JSON
    const jsonString = match[1].trim();
    try {
      const graphData = JSON.parse(jsonString) as GraphData;
      
      // Validate that it has at least a data property
      if (graphData && Array.isArray(graphData.data)) {
        segments.push({
          type: "graph",
          data: graphData,
          id: `${messageId}-graph-${graphIndex}`,
        });
        graphIndex++;
      } else {
        // Invalid graph structure, treat as text
        console.warn("Invalid graph data structure:", jsonString);
        segments.push({
          type: "text",
          content: match[0],
        });
      }
    } catch (error) {
      // JSON parse error, keep as text
      console.warn("Failed to parse graph JSON:", error);
      segments.push({
        type: "text",
        content: match[0],
      });
    }

    lastIndex = match.index + match[0].length;
  }

  // Add remaining text after the last graph block
  if (lastIndex < content.length) {
    const textContent = content.slice(lastIndex).trim();
    if (textContent) {
      segments.push({ type: "text", content: textContent });
    }
  }

  // If no graphs were found, return the original content as a single text segment
  if (segments.length === 0 && content.trim()) {
    segments.push({ type: "text", content: content });
  }

  return { segments };
}

/**
 * Checks if the content contains any graph blocks
 */
export function hasGraphContent(content: string): boolean {
  return /<graph>[\s\S]*?<\/graph>/i.test(content);
}
