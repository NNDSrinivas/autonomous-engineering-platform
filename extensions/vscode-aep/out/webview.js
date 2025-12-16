"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const react_1 = require("react");
const client_1 = require("react-dom/client");
const NaviPanel_1 = require("./components/NaviPanel");
// Initialize React app in the webview
const container = document.getElementById('root');
if (container) {
    const root = client_1.default.createRoot(container);
    root.render(<NaviPanel_1.default />);
}
else {
    console.error('[NAVI] Root container not found. Make sure the HTML has a div with id="root"');
}
// Export for potential direct usage
exports.default = NaviPanel_1.default;
//# sourceMappingURL=webview.js.map