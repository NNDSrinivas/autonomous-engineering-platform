"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
function activate(context) {
    console.log('AEP MINIMAL: Starting activation');
    // Show immediate confirmation
    vscode.window.showInformationMessage('AEP Extension activated!');
    // Create the simplest possible webview provider
    const provider = {
        resolveWebviewView(webviewView) {
            console.log('AEP MINIMAL: resolveWebviewView called');
            vscode.window.showInformationMessage('AEP View Provider resolved!');
            webviewView.webview.options = {
                enableScripts: true
            };
            webviewView.webview.html = `
                <!DOCTYPE html>
                <html>
                <head><title>AEP Test</title></head>
                <body style="padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                    <h1>🎉 AEP Extension Working!</h1>
                    <p>The view provider is now registered and working correctly.</p>
                    <p>No more "no data provider" error!</p>
                </body>
                </html>
            `;
        }
    };
    // Register the provider
    const disposable = vscode.window.registerWebviewViewProvider('aep.welcome', provider);
    context.subscriptions.push(disposable);
    console.log('AEP MINIMAL: Provider registered for aep.welcome');
    vscode.window.showInformationMessage('AEP Provider registered successfully!');
}
function deactivate() { }
//# sourceMappingURL=extension.js.map