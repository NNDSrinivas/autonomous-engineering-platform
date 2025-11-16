# 🧠 NAVI Enhanced Backend Testing Guide

NAVI now has a **real brain** with rich context awareness! This guide shows how to test the enhanced backend integration with editor context, model/mode selection, and intelligent responses.

## 🚀 Quick Start with Enhanced Backend

### 1. Start the Enhanced Backend

```bash
cd extensions/vscode-aep
npm run enhanced-backend
```

You should see:
```
🦊 Enhanced NAVI Backend running at http://127.0.0.1:8787
💬 Chat endpoint: POST http://127.0.0.1:8787/api/chat
✨ New Features:
   • Rich context payloads (editor, model, mode)
   • Code-aware responses
   • Context-sensitive assistance
   • Streaming infrastructure ready
```

### 2. Configure VS Code Settings

1. Open VS Code Settings (Cmd/Ctrl + ,)
2. Search for "aep navi"
3. Set **AEP: Navi Backend Url** to: `http://127.0.0.1:8787/api/chat`

Or add to your `settings.json`:
```json
{
  "aep.naviBackendUrl": "http://127.0.0.1:8787/api/chat"
}
```

### 3. Test Rich Context Integration

#### 🎯 **Test Scenario 1: Code Selection Analysis**
1. Open any source code file (`.js`, `.py`, `.ts`, etc.)
2. **Select some code** (function, class, or code block)  
3. In NAVI chat, ask: *"Explain this code"* or *"What does this do?"*
4. Watch NAVI analyze the selection with language-specific context!

#### 🎯 **Test Scenario 2: Debugging Assistance**  
1. Select problematic code in your editor
2. Ask NAVI: *"Fix this bug"* or *"Debug this function"*
3. See context-aware debugging suggestions with code analysis

#### 🎯 **Test Scenario 3: Test Generation**
1. Select a function or class
2. Ask: *"Write unit tests for this"* or *"Generate test coverage"*  
3. Get intelligent test suggestions based on the selected code

#### 🎯 **Test Scenario 4: Model & Mode Switching**
1. Click the **Model dropdown** → select different AI models
2. Click the **Mode dropdown** → switch between Agent/Chat modes
3. Send messages and see model/mode-specific responses

#### 🎯 **Test Scenario 5: File Context Awareness**
1. Open any project file  
2. Ask: *"Analyze this file"* or *"Document this code"*
3. NAVI will show awareness of filename, language, and context

## 🔧 Enhanced API Contract

The new backend receives rich payloads:

**POST** `/api/chat`
```json
{
  "message": "User's message text",
  "model": "ChatGPT 5.1",
  "mode": "Agent (full access)", 
  "editor": {
    "fileName": "/path/to/file.js",
    "languageId": "javascript",
    "selection": "selected code text or null"
  },
  "conversationId": null,
  "history": []
}
```

**Response:**
```json
{
  "reply": "Context-aware AI response",
  "meta": {
    "model_used": "ChatGPT 5.1",
    "finish_reason": "stop",
    "usage": {
      "input_tokens": 45,
      "output_tokens": 120,
      "total_tokens": 165
    }
  }
}
```

## 🎨 **What's New in the Enhanced Brain**

### ✨ **Rich Context Integration**
- **Editor Awareness**: Knows current file, language, and selected text
- **Model Selection**: Respects chosen AI model (ChatGPT 5.1, Claude, etc.)
- **Mode Sensitivity**: Responds differently in Agent vs Chat mode
- **Smart Responses**: Code analysis, debugging help, test generation

### 🎯 **Contextual Response Types**
- **Code Explanation**: When you select code and ask "explain this"
- **Debug Assistance**: Intelligent debugging for selected code blocks  
- **Test Generation**: Smart unit test creation based on functions/classes
- **File Analysis**: Whole-file understanding and documentation
- **Agent Actions**: Full workspace access in Agent mode
- **Chat Guidance**: Read-only help and explanations in Chat mode

### 🔮 **Streaming Ready Infrastructure**
- Backend includes streaming scaffolding
- Extension has `streamReplyToWebview()` helper ready
- Easy to plug in real OpenAI/Claude streaming
- Future: Real-time token-by-token responses

## 🚀 **Connect Real AI Services**

The enhanced backend is ready for real AI integration:

### **OpenAI GPT-4 Integration**
```javascript
const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

const messages = [
  { role: 'system', content: `You are NAVI, a VS Code assistant. Current context: ${editor.fileName} (${editor.languageId})` },
  { role: 'user', content: message }
];

if (editor.selection) {
  messages.push({ 
    role: 'system', 
    content: `Selected code:\n\`\`\`${editor.languageId}\n${editor.selection}\n\`\`\`` 
  });
}

const response = await openai.chat.completions.create({
  model: 'gpt-4',
  messages,
  stream: true // Enable streaming!
});
```

### **Anthropic Claude Integration**
```javascript
const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

const contextPrompt = editor.selection 
  ? `Analyze this ${editor.languageId} code:\n\`\`\`\n${editor.selection}\n\`\`\``
  : `Working in ${editor.fileName} (${editor.languageId})`;

const response = await anthropic.messages.create({
  model: 'claude-3-5-sonnet-20241022',
  messages: [
    { role: 'user', content: `${contextPrompt}\n\nUser request: ${message}` }
  ],
  stream: true
});
```

### **Local LLM Integration (Ollama)**
```bash
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "codellama", 
    "prompt": "File: '${editor.fileName}' (${editor.languageId})\nSelected: '${editor.selection}'\nRequest: '${message}'",
    "stream": true
  }'
```

## 🔍 **Advanced Testing Scenarios**

### **Multi-Language Code Analysis**
1. Open files in different languages (Python, TypeScript, Rust, Go)
2. Select code in each and ask similar questions
3. See language-specific responses and suggestions

### **Complex Selection Context**
1. Select multi-line functions with dependencies
2. Ask for refactoring or optimization suggestions
3. Test with classes, interfaces, and complex logic

### **Mode-Specific Behavior**  
1. **Agent Mode**: Ask NAVI to "create a new file" or "run tests"
2. **Chat Mode**: Ask the same - see the different response approach
3. Switch modes mid-conversation and observe behavior changes

### **Model Personality Testing**
1. Select the same code, ask the same question with different models
2. **ChatGPT 5.1**: Advanced reasoning responses
3. **Claude 3.5 Sonnet**: Creative and detailed explanations  
4. **GPT-4 Turbo**: Fast, efficient technical answers
5. **Local LLM**: Privacy-focused, local processing

## 🛟 **Troubleshooting**

**Backend not receiving context?**
- Check VS Code Developer Tools (Help → Toggle Developer Tools)  
- Look for POST requests to `/api/chat` with full payload
- Verify model/mode values are being sent correctly

**Context not showing in responses?**
- Ensure you have a file open and code selected
- Check the backend console logs for received context
- Verify the enhanced backend (port 8787) is running, not the simple demo (port 8000)

**Model/Mode selection not working?**
- Click directly on the model/mode pills to open dropdowns
- Check browser console for any JavaScript errors
- Reload the extension (Cmd/Ctrl + Shift + P → "Developer: Reload Window")

## 🎯 **What's Next?**

Ready to level up NAVI even more? Next we can add:

1. **🔥 Real Streaming**: Token-by-token responses for that live AI feel
2. **🛠 Code Actions**: "Fix this", "Add tests", "Refactor" with real file changes  
3. **📁 Workspace Tools**: Project analysis, dependency management, file creation
4. **🔌 MCP Integration**: Connect to databases, APIs, and external tools
5. **💾 Conversation Memory**: Persistent chat history and context retention

NAVI now has the brains - let's give it the tools! 🧠⚡