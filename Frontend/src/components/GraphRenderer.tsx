import { useEffect, useRef, memo } from "react";
import type { Data, Layout, Config, PlotlyHTMLElement } from "plotly.js";

declare global {
  interface Window {
    Plotly: {
      newPlot: (
        root: HTMLDivElement,
        data: Data[],
        layout?: Partial<Layout>,
        config?: Partial<Config>
      ) => Promise<PlotlyHTMLElement>;
      purge: (root: HTMLDivElement) => void;
    };
  }
}

export interface GraphData {
  data: Data[];
  layout?: Partial<Layout>;
  config?: Partial<Config>;
}

interface GraphRendererProps {
  graphData: GraphData;
  id: string;
}

const GraphRenderer = memo(({ graphData, id }: GraphRendererProps) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !window.Plotly) return;

    const defaultLayout: Partial<Layout> = {
      autosize: true,
      margin: { l: 50, r: 30, t: 40, b: 50 },
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      font: { color: "#e0e0e0", size: 12 },
      xaxis: {
        gridcolor: "rgba(255,255,255,0.1)",
        zerolinecolor: "rgba(255,255,255,0.2)",
      },
      yaxis: {
        gridcolor: "rgba(255,255,255,0.1)",
        zerolinecolor: "rgba(255,255,255,0.2)",
      },
    };

    const defaultConfig: Partial<Config> = {
      responsive: true,
      displayModeBar: true,
      displaylogo: false,
      modeBarButtonsToRemove: ["lasso2d", "select2d"],
    };

    const mergedLayout = { ...defaultLayout, ...graphData.layout };
    const mergedConfig = { ...defaultConfig, ...graphData.config };

    window.Plotly.newPlot(
      containerRef.current,
      graphData.data,
      mergedLayout,
      mergedConfig
    );

    // Cleanup on unmount
    return () => {
      if (containerRef.current) {
        window.Plotly.purge(containerRef.current);
      }
    };
  }, [graphData]);

  return (
    <div
      ref={containerRef}
      id={`graph-${id}`}
      className="plotly-graph-container"
      style={{ width: "100%", minHeight: "350px" }}
    />
  );
});

GraphRenderer.displayName = "GraphRenderer";

export default GraphRenderer;
