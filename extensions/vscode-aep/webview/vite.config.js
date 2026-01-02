"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const vite_1 = require("vite");
const plugin_react_1 = require("@vitejs/plugin-react");
const path_1 = require("path");
exports.default = (0, vite_1.defineConfig)({
    plugins: [(0, plugin_react_1.default)()],
    root: ".",
    base: "",
    build: {
        outDir: "../dist/webview",
        emptyOutDir: true,
        sourcemap: true,
        rollupOptions: {
            input: (0, path_1.resolve)(__dirname, "index.html"),
            output: {
                entryFileNames: "panel.js",
                chunkFileNames: "chunks/[name].js",
                assetFileNames: "assets/[name][extname]"
            }
        }
    }
});
//# sourceMappingURL=vite.config.js.map