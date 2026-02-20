import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  plugins: [react()],
  root: ".",
  base: "",
  server: {
    fs: {
      allow: [
        resolve(__dirname, "../../../shared"),
        resolve(__dirname, "../../../.."),
      ],
    },
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
      "@shared": resolve(__dirname, "../../../shared"),
    }
  },
  optimizeDeps: {
    include: ["lucide-react"]
  },
  build: {
    outDir: "../dist/webview",
    emptyOutDir: true,
    sourcemap: true,
    commonjsOptions: {
      include: [/lucide-react/, /node_modules/]
    },
    rollupOptions: {
      input: resolve(__dirname, "index.html"),
      output: {
        entryFileNames: "panel.js",
        chunkFileNames: "chunks/[name].js",
        assetFileNames: "assets/[name][extname]",
        manualChunks: {
          'lucide': ['lucide-react']
        }
      }
    }
  }
});
