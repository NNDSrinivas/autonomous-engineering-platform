/**
 * NAVI Streaming Implementation for NaviChatPanel.tsx
 *
 * This file shows how to implement streaming responses in the frontend.
 * Copy the relevant parts into your NaviChatPanel.tsx component.
 */

import { fetchEventSource } from '@microsoft/fetch-event-source';
import { useState } from 'react';

// ============================================================================
// STEP 1: Add State for Streaming
// ============================================================================

const NaviChatPanel = () => {
  // Add these state variables
  const [streamingStatus, setStreamingStatus] = useState<string>('');
  const [streamingProgress, setStreamingProgress] = useState<{ step: number; total: number } | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);

  // ... rest of your component state

  // ============================================================================
  // STEP 2: Create Streaming Function
  // ============================================================================

  const sendMessageWithStreaming = async (message: string) => {
    setIsStreaming(true);
    setStreamingStatus('Preparing request...');
    setStreamingProgress(null);

    try {
      await fetchEventSource('http://localhost:8787/api/navi/process/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message,
          workspace: workspacePath || '/tmp',
          llm_provider: selectedProvider || 'openai',
          llm_model: selectedModel || null,
        }),

        onmessage(event) {
          try {
            const data = JSON.parse(event.data);

            switch (data.type) {
              case 'status':
                // Update status message and progress
                setStreamingStatus(data.message);
                if (data.step && data.total) {
                  setStreamingProgress({ step: data.step, total: data.total });
                }
                break;

              case 'result':
                // Handle the final result
                setIsStreaming(false);
                setStreamingStatus('');
                setStreamingProgress(null);

                // Add message to chat
                addMessageToChat({
                  role: 'assistant',
                  content: data.data.message,
                  files: data.data.files_created || [],
                  commands: data.data.commands_run || [],
                });
                break;

              case 'done':
                // Stream finished
                setIsStreaming(false);
                setStreamingStatus('');
                setStreamingProgress(null);
                break;

              case 'error':
                // Handle error
                setIsStreaming(false);
                setStreamingStatus('');
                setStreamingProgress(null);
                console.error('Streaming error:', data.message);
                // Show error to user
                addMessageToChat({
                  role: 'assistant',
                  content: `Error: ${data.message}`,
                  isError: true,
                });
                break;
            }
          } catch (e) {
            console.error('Failed to parse stream event:', e);
          }
        },

        onerror(err) {
          console.error('Stream connection error:', err);
          setIsStreaming(false);
          setStreamingStatus('');
          setStreamingProgress(null);

          // Optionally fall back to regular endpoint
          // fallbackToRegularEndpoint(message);
          throw err; // Stop retrying
        },
      });
    } catch (error) {
      console.error('Streaming failed:', error);
      setIsStreaming(false);
      setStreamingStatus('');
      setStreamingProgress(null);
    }
  };

  // ============================================================================
  // STEP 3: Update Send Message Handler
  // ============================================================================

  const handleSendMessage = async (message: string) => {
    // Add user message to chat immediately
    addMessageToChat({
      role: 'user',
      content: message,
    });

    // Use streaming
    await sendMessageWithStreaming(message);
  };

  // ============================================================================
  // STEP 4: Add Streaming UI Component
  // ============================================================================

  return (
    <div className="navi-chat-panel">
      {/* ... existing chat messages ... */}

      {/* Streaming Status UI */}
      {isStreaming && (
        <div className="streaming-status-container">
          <div className="streaming-spinner" />
          <div className="streaming-content">
            <div className="streaming-message">{streamingStatus}</div>
            {streamingProgress && (
              <div className="streaming-progress">
                <div className="progress-bar">
                  <div
                    className="progress-fill"
                    style={{
                      width: `${(streamingProgress.step / streamingProgress.total) * 100}%`,
                    }}
                  />
                </div>
                <div className="progress-text">
                  Step {streamingProgress.step} of {streamingProgress.total}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ... rest of your UI ... */}
    </div>
  );
};

// ============================================================================
// STEP 5: Add CSS Styles
// ============================================================================

/*
Add these styles to NaviChatPanel.css:

.streaming-status-container {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  margin: 8px 0;
  background: var(--vscode-editor-background);
  border: 1px solid var(--vscode-panel-border);
  border-radius: 6px;
  font-size: 14px;
}

.streaming-spinner {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  border: 2px solid var(--vscode-progressBar-background);
  border-top-color: var(--vscode-button-background);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.streaming-content {
  flex: 1;
  min-width: 0;
}

.streaming-message {
  color: var(--vscode-foreground);
  font-weight: 500;
  margin-bottom: 8px;
}

.streaming-progress {
  margin-top: 8px;
}

.progress-bar {
  width: 100%;
  height: 4px;
  background: var(--vscode-progressBar-background);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 4px;
}

.progress-fill {
  height: 100%;
  background: var(--vscode-button-background);
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 12px;
  color: var(--vscode-descriptionForeground);
}
*/

// ============================================================================
// ALTERNATIVE: Fallback to Regular Endpoint
// ============================================================================

const fallbackToRegularEndpoint = async (message: string) => {
  try {
    const response = await fetch('http://localhost:8787/api/navi/process', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message,
        workspace: workspacePath,
        llm_provider: selectedProvider,
      }),
    });

    const result = await response.json();

    if (result.success) {
      addMessageToChat({
        role: 'assistant',
        content: result.message,
        files: result.files_created || [],
      });
    }
  } catch (error) {
    console.error('Fallback failed:', error);
  }
};

// ============================================================================
// TESTING
// ============================================================================

/*
To test the streaming implementation:

1. Make sure backend is running:
   cd /Users/mounikakapa/dev/autonomous-engineering-platform
   source aep-venv/bin/activate
   NAVI_DISABLE_MEMORY_CONTEXT=true python -m uvicorn backend.api.main:app --port 8787

2. In VS Code extension, send a message and you should see:
   🎯 Analyzing your request... [1/6]
   📋 Loading workspace context... [2/6]
   🔍 Understanding your code... [3/6]
   🤖 Connecting to AI model... [4/6]
   ✨ Generating response... [5/6]
   ✅ Complete! [6/6]

3. First feedback appears in <0.2s instead of waiting 6+ seconds!
*/

export default NaviChatPanel;
