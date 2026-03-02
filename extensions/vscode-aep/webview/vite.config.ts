import { defineConfig, searchForWorkspaceRoot } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  plugins: [react()],
  root: ".",
  base: "",
  server: {
    port: 3008,
    fs: {
      // Allow access to entire workspace
      allow: [searchForWorkspaceRoot(process.cwd())],
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
    // The webview bundle is intentionally larger than a typical SPA chunk.
    // Keep the warning signal meaningful for this target.
    chunkSizeWarningLimit: 1200,
    commonjsOptions: {
      include: [/lucide-react/, /node_modules/]
    },
    rollupOptions: {
      input: resolve(__dirname, "index.html"),
      output: {
        entryFileNames: "panel.js",
        chunkFileNames: "chunks/[name].js",
        assetFileNames: "assets/[name][extname]",
        manualChunks: (id: string) => {
          if (!id.includes("node_modules")) return;
          if (id.includes("@radix-ui")) return "radix";
          if (id.includes("lucide-react")) return "lucide";
          if (
            id.includes("prismjs") ||
            id.includes("react-syntax-highlighter") ||
            id.includes("remark-prism")
          ) {
            return "syntax";
          }
          if (id.includes("react-markdown") || id.includes("remark-gfm")) return "markdown";
          if (id.includes("@tanstack/react-query") || id.includes("zustand") || id.includes("immer")) return "state";
          if (id.includes("@supabase")) return "supabase";
          if (id.includes("@microsoft/fetch-event-source")) return "sse";
          if (id.includes("react") || id.includes("scheduler") || id.includes("use-sync-external-store")) return "react-vendor";
        }
      }
    }
  }
});
