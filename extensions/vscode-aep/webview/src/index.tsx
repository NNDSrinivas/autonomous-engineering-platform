import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./globals.css";

const debugEnabled = (() => {
  if (typeof window === "undefined") return false;
  const anyWindow = window as any;
  if (anyWindow.__AEP_DEBUG__ === true) return true;
  try {
    return localStorage.getItem("aep:debug") === "1";
  } catch {
    return false;
  }
})();

if (import.meta.env.PROD && !debugEnabled) {
  // Silence debug logging in production webview unless explicitly enabled.
  console.log = () => {};
  console.debug = () => {};
}

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("Root element #root not found in panel.html");
}

const root = createRoot(rootEl);
root.render(<App />);
