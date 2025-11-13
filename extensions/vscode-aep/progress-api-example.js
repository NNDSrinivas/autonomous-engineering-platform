"use strict";
// Example: How to integrate the new progress API with your backend
// In your extension's message handler:
panel.webview.onDidReceiveMessage(async (msg) => {
    if (msg.type === 'send') {
        // Start your agent/backend work
        const userQuery = msg.text;
        try {
            // Call your agent with progress callbacks
            await processWithAgent(userQuery, {
                onProgress: (file, added, removed) => {
                    panel.webview.postMessage({
                        type: 'progress',
                        file: !!file,
                        added,
                        removed
                    });
                },
                onComplete: (changes) => {
                    // Show changes card
                    panel.webview.postMessage({
                        type: 'diff',
                        items: changes
                    });
                    // Mark as done (triggers celebrate animation + resets counters)
                    panel.webview.postMessage({ type: 'done' });
                    // Send final assistant message
                    panel.webview.postMessage({
                        type: 'assistant',
                        text: "✅ **Changes applied successfully!**\n\nI've updated the files as requested. See the changes summary above."
                    });
                }
            });
        }
        catch (error) {
            panel.webview.postMessage({ type: 'done' });
            panel.webview.postMessage({
                type: 'assistant',
                text: `❌ **Error occurred:** ${error.message}`
            });
        }
    }
});
// Example backend integration:
async function processWithAgent(query, callbacks) {
    // Example: streaming file edits from your agent
    const files = await yourAgent.planEdits(query);
    const allChanges = [];
    for (const fileEdit of files) {
        // Apply the edit
        const result = await yourAgent.applyEdit(fileEdit);
        // Report progress
        callbacks.onProgress(result.path, result.linesAdded, result.linesRemoved);
        // Track for final summary
        allChanges.push({
            path: result.path,
            added: result.linesAdded,
            removed: result.linesRemoved
        });
        // Small delay for better UX
        await new Promise(resolve => setTimeout(resolve, 200));
    }
    // Report completion
    callbacks.onComplete(allChanges);
}
// Message types supported:
// 
// progress: { type: 'progress', file: boolean, added?: number, removed?: number }
// diff: { type: 'diff', items: Array<{path: string, added?: number, removed?: number}> }
// done: { type: 'done' } // triggers celebrate + resets counters after 800ms
// assistant: { type: 'assistant', text: string } // normal message
//# sourceMappingURL=progress-api-example.js.map