import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./globals.css";

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("Root element #root not found in panel.html");
}

const root = createRoot(rootEl);
root.render(<App />);