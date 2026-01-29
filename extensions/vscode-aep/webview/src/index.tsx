import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./globals.css";

if (import.meta.env.PROD) {
  // Silence debug logging in production webview.
  console.log = () => {};
  console.debug = () => {};
}

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("Root element #root not found in panel.html");
}

const root = createRoot(rootEl);
root.render(<App />);
