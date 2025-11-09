import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext) {
    console.log('AEP MINIMAL: Starting activation');
    
    // Show immediate confirmation
    vscode.window.showInformationMessage('AEP Extension activated!');
    
    // Create the simplest possible webview provider
    const provider = {
        resolveWebviewView(webviewView: vscode.WebviewView) {
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

export function deactivate() {}