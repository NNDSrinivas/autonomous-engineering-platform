# Monitoring Claude Code Chat Panel Logs

## Quick Start

### Option 1: VS Code Output Panel (Recommended)
1. Open VS Code with your extension running
2. Press `Cmd+Shift+U` (Mac) or `Ctrl+Shift+U` (Windows/Linux)
3. From the dropdown in the Output panel, select **"Extension Host"**
4. You'll see all extension logs in real-time with `[AEP]` prefix

### Option 2: Developer Tools Console
1. In VS Code, go to **Help > Toggle Developer Tools**
2. Click the **Console** tab
3. Filter by typing `[AEP]` in the filter box
4. You'll see all extension console logs

### Option 3: Debug Console (During Development)
1. Press `F5` to run the extension in debug mode
2. In the main VS Code window, open **View > Debug Console**
3. All console.log output will appear here

## Key Log Patterns

### Chat Request Flow
```
[AEP] 📡 About to fetch streaming URL: <url>
  ↓
[AEP] 🎬 Sending botMessageStart with messageId: <id>
  ↓
[AEP] 📝 V2 Text chunk: ...
  ↓
[AEP] ✅ Response sent to webview (streaming: true)
```

### Error Indicators
- `[AEP] ❌` - Critical errors
- `[AEP] ⚠️` - Warnings
- `[AEP] Streaming failed, falling back` - Stream errors

### Request Types
- `[AEP] 🚀 Using V2 tool-use streaming` - Standard chat
- `[AEP] 🤖 Using Autonomous mode` - Autonomous operations
- `[AEP] 🏢 Enterprise mode requested` - Enterprise mode

### Timeout Monitoring
Look for:
- `Request timed out` - Request exceeded timeout
- `Connection timeout` - SSE connection timeout
- `Heartbeat timeout` - Lost connection to backend

## Important Configuration

### Current Timeout Settings
- **Standard Chat**: 10 minutes (600000 ms)
- **Autonomous Operations**: 90 minutes (configurable)
- **SSE Connection**: Uses autonomous timeout
- **Heartbeat Interval**: 15 seconds

### Where Timeouts Are Defined
See `src/extension.ts:46-49`:
```typescript
const DEFAULT_REQUEST_TIMEOUT_MS = 600000;
const DEFAULT_AUTONOMOUS_REQUEST_TIMEOUT_MINUTES = 90;
const DEFAULT_AUTONOMOUS_REQUEST_TIMEOUT_MS = ...;
const DEFAULT_HEARTBEAT_INTERVAL_MS = 15000;
```

## Troubleshooting

### Chat Panel Not Responding
1. Check Extension Host logs for:
   - `[AEP] ⚠️ No auth token available`
   - `[AEP] ❌ Backend streaming error`
   - Timeout messages
   - Connection errors

2. Check network requests in Developer Tools:
   - Go to Network tab
   - Filter for `/api/navi/chat`
   - Check request status and response

3. Verify backend is running:
   - Check backend URL in settings
   - Test backend health endpoint

### Common Issues

#### "Request timed out"
- Increase timeout in settings
- Check if backend is processing slowly
- Look for long-running operations

#### "Streaming failed, falling back"
- Check SSE connection in Network tab
- Verify firewall isn't blocking EventSource
- Check backend streaming support

#### No logs appearing
- Ensure extension is activated
- Check Output panel is set to "Extension Host"
- Try reloading window (Cmd+R / Ctrl+R)

## Monitoring Script

Run the monitoring helper script:
```bash
./scripts/monitor-logs.sh
```

This will show you:
- How to access logs
- Key patterns to watch for
- Recent log file locations
