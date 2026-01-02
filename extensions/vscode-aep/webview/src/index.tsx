import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./globals.css";

console.log('🚨 INDEX.TSX: Entry point started!');
console.log('🚨 INDEX.TSX: App component imported:', App);
console.log('🚨 INDEX.TSX: App component name:', App.name);

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("Root element #root not found in panel.html");
}

console.log('🚨 INDEX.TSX: About to create root and render App');
const root = createRoot(rootEl);
root.render(<App />);
console.log('🚨 INDEX.TSX: App render called');
