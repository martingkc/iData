declare module "plotly.js-dist" {
  export * from "plotly.js";
  import Plotly from "plotly.js";
  export default Plotly;
}

declare module "plotly.js" {
  export interface Data {
    type?: string;
    x?: (string | number | Date)[];
    y?: (string | number | Date)[];
    z?: (string | number | Date)[][] | (string | number | Date)[];
    values?: (string | number)[];
    labels?: string[];
    text?: string | string[];
    name?: string;
    mode?: string;
    marker?: {
      color?: string | string[] | number[];
      size?: number | number[];
      symbol?: string;
      line?: { color?: string; width?: number };
      colorscale?: string | [number, string][];
    };
    line?: {
      color?: string;
      width?: number;
      dash?: string;
      shape?: string;
    };
    fill?: string;
    fillcolor?: string;
    hoverinfo?: string;
    hovertemplate?: string;
    textinfo?: string;
    textposition?: string;
    hole?: number;
    orientation?: string;
    [key: string]: unknown;
  }

  export interface Layout {
    title?: string | { text?: string; font?: { size?: number; color?: string } };
    autosize?: boolean;
    width?: number;
    height?: number;
    margin?: { l?: number; r?: number; t?: number; b?: number; pad?: number };
    paper_bgcolor?: string;
    plot_bgcolor?: string;
    font?: { family?: string; size?: number; color?: string };
    showlegend?: boolean;
    legend?: { x?: number; y?: number; orientation?: string };
    xaxis?: AxisLayout;
    yaxis?: AxisLayout;
    barmode?: string;
    bargap?: number;
    bargroupgap?: number;
    hovermode?: string | boolean;
    annotations?: unknown[];
    shapes?: unknown[];
    [key: string]: unknown;
  }

  export interface AxisLayout {
    title?: string | { text?: string };
    type?: string;
    range?: [number, number];
    autorange?: boolean | string;
    tickformat?: string;
    tickangle?: number;
    showgrid?: boolean;
    gridcolor?: string;
    gridwidth?: number;
    zeroline?: boolean;
    zerolinecolor?: string;
    zerolinewidth?: number;
    showline?: boolean;
    linecolor?: string;
    linewidth?: number;
    [key: string]: unknown;
  }

  export interface Config {
    responsive?: boolean;
    displayModeBar?: boolean | "hover";
    displaylogo?: boolean;
    modeBarButtonsToRemove?: string[];
    modeBarButtonsToAdd?: string[];
    scrollZoom?: boolean;
    editable?: boolean;
    staticPlot?: boolean;
    toImageButtonOptions?: {
      format?: string;
      filename?: string;
      height?: number;
      width?: number;
      scale?: number;
    };
    [key: string]: unknown;
  }

  export interface PlotlyHTMLElement extends HTMLDivElement {
    data: Data[];
    layout: Layout;
  }

  export function newPlot(
    root: string | HTMLDivElement,
    data: Data[],
    layout?: Partial<Layout>,
    config?: Partial<Config>
  ): Promise<PlotlyHTMLElement>;

  export function purge(root: string | HTMLDivElement): void;
  export function react(
    root: string | HTMLDivElement,
    data: Data[],
    layout?: Partial<Layout>,
    config?: Partial<Config>
  ): Promise<PlotlyHTMLElement>;
  export function relayout(
    root: string | HTMLDivElement,
    layout: Partial<Layout>
  ): Promise<PlotlyHTMLElement>;
}
