# NAVI Backend Integration Testing

This guide shows how to test the NAVI VS Code extension with a real HTTP backend.

## 🚀 Quick Start

### 1. Start the Demo Backend

```bash
cd extensions/vscode-aep
npm run demo-backend
```

You should see:
```
🦊 NAVI Demo Backend running at http://localhost:8000
💬 Chat endpoint: POST http://localhost:8000/api/chat
🔍 Health check: GET http://localhost:8000/api/health
```

### 2. Configure VS Code Settings

1. Open VS Code Settings (Cmd/Ctrl + ,)
2. Search for "aep navi"
3. Set **AEP: Navi Backend Url** to: `http://localhost:8000`

Or add to your `settings.json`:
```json
{
  "aep.naviBackendUrl": "http://localhost:8000"
}
```

### 3. Test the Integration

1. Open the AEP view in VS Code (fox icon in sidebar)
2. Type a message to NAVI
3. Watch for the typing indicator ("NAVI is thinking...")
4. See the backend response!

## 🔧 Backend API Contract

The extension expects backends to implement this simple API:

**POST** `/api/chat`
```json
{
  "message": "User's message text"
}
```

**Response:**
```json
{
  "reply": "Assistant's response text"
}
```

## 🦊 Connecting Real AI Services

Replace the demo backend with real AI:

### OpenAI Integration
```javascript
const response = await openai.chat.completions.create({
  model: "gpt-4",
  messages: [{ role: "user", content: message }]
});
const reply = response.choices[0].message.content;
```

### Anthropic Claude
```javascript
const response = await anthropic.messages.create({
  model: "claude-3-sonnet-20240229",
  messages: [{ role: "user", content: message }]
});
const reply = response.content[0].text;
```

### Local LLM (Ollama)
```bash
curl http://localhost:11434/api/generate \\
  -d '{"model": "llama2", "prompt": "message", "stream": false}'
```

## 🔍 Troubleshooting

**Backend not responding?**
- Check the demo backend is running: `npm run demo-backend`
- Verify the URL in VS Code settings matches the backend
- Check the VS Code Output panel (AEP channel) for errors

**CORS errors?**
- The demo backend includes CORS headers
- For custom backends, add: `app.use(cors())`

**TypeScript compilation errors?**
- Run: `npm run compile`
- Check the Problems panel in VS Code