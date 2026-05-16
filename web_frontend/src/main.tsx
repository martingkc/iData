import React from "react";
import ReactDOM from "react-dom/client";
import Plotly from "plotly.js-dist";
import App from "./App";
import "./theme.css";
import "./styles.css";
import "@fortawesome/fontawesome-free/css/all.min.css";

// Make Plotly available globally for the GraphRenderer component
(window as unknown as { Plotly: typeof Plotly }).Plotly = Plotly;

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
