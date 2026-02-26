"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const vite_1 = require("vite");
const plugin_react_1 = require("@vitejs/plugin-react");
const path_1 = require("path");
exports.default = (0, vite_1.defineConfig)({
    plugins: [(0, plugin_react_1.default)()],
    root: ".",
    base: "",
    server: {
        fs: {
            allow: [(0, path_1.resolve)(__dirname, "../../../shared")]
        }
    },
    resolve: {
        alias: {
            "@": (0, path_1.resolve)(__dirname, "src"),
            "@shared": (0, path_1.resolve)(__dirname, "../../../shared")
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
            input: (0, path_1.resolve)(__dirname, "index.html"),
            output: {
                entryFileNames: "panel.js",
                chunkFileNames: "chunks/[name].js",
                assetFileNames: "assets/[name][extname]",
                manualChunks: (id) => {
                    if (!id.includes("node_modules"))
                        return;
                    if (id.includes("@radix-ui"))
                        return "radix";
                    if (id.includes("lucide-react"))
                        return "lucide";
                    if (id.includes("prismjs") ||
                        id.includes("react-syntax-highlighter") ||
                        id.includes("remark-prism")) {
                        return "syntax";
                    }
                    if (id.includes("react-markdown") || id.includes("remark-gfm"))
                        return "markdown";
                    if (id.includes("@tanstack/react-query") || id.includes("zustand") || id.includes("immer"))
                        return "state";
                    if (id.includes("@supabase"))
                        return "supabase";
                    if (id.includes("@microsoft/fetch-event-source"))
                        return "sse";
                    if (id.includes("react") || id.includes("scheduler") || id.includes("use-sync-external-store"))
                        return "react-vendor";
                }
            }
        }
    }
});
//# sourceMappingURL=vite.config.js.map
