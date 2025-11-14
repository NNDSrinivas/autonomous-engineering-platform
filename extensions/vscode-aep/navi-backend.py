# main.py - Sample FastAPI backend for NAVI with streaming support
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, AsyncGenerator, List
import json
import asyncio
import time

app = FastAPI()

# Enable CORS for VS Code extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    id: str
    model: Optional[str] = "ChatGPT 5.1"
    mode: Optional[str] = "Agent (full access)"
    messages: List[ChatMessage] = []
    stream: Optional[bool] = False
    context: Optional[Dict[str, Any]] = None

SYSTEM_PROMPT = """You are NAVI, an autonomous engineering assistant living inside VS Code.
- Be concise, but helpful.
- Prefer concrete steps and code examples.
- When the user asks you to read files / run commands, answer conceptually for now.
- Use markdown for lists and code, with triple backticks for code blocks.
"""

@app.post("/api/chat")
async def chat(request: Request):
    stream_flag = request.query_params.get("stream")
    body = await request.json()
    payload = ChatRequest(**body)
    
    # Get the latest user message
    user_message = ""
    if payload.messages:
        last_message = payload.messages[-1]
        if last_message.role == "user":
            user_message = last_message.content
    
    print(f"Received conversation ID: {payload.id}")
    print(f"Latest user message: {user_message}")
    print(f"Message history: {len(payload.messages)} messages")
    
    if stream_flag == "1":
        # --- Streaming response ---
        async def event_stream() -> AsyncGenerator[str, None]:
            # Simulate a smart response based on context
            response = generate_contextual_response(payload)
            
            # Stream the response word by word
            words = response.split()
            for i, word in enumerate(words):
                if i > 0:
                    word = " " + word
                
                data = json.dumps({"delta": word})
                yield f"data: {data}\n\n"
                
                # Small delay to simulate streaming
                await asyncio.sleep(0.1)
            
            # Signal completion
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
        )
    
    else:
        # --- Non-streaming response ---
        response = generate_contextual_response(payload)
        return JSONResponse({"reply": response})

def generate_contextual_response(payload: ChatRequest) -> str:
    """Generate a contextual response based on the user's message and VS Code context"""
    # Extract the latest user message
    user_message = ""
    if payload.messages:
        last_message = payload.messages[-1]
        if last_message.role == "user":
            user_message = last_message.content
    
    message = user_message.lower()
    context = payload.context or {}
    
    # Extract context info
    active_file = context.get('activeFile')
    active_language = context.get('activeLanguageId')
    selection_text = context.get('selectionText')
    workspace_root = context.get('workspaceRoot', {})
    
    # Context-aware responses
    if active_file:
        file_name = active_file.split('/')[-1] if '/' in active_file else active_file
        
        if selection_text and len(selection_text.strip()) > 0:
            return f"""I can see you have code selected in **{file_name}** ({active_language}):

```{active_language or 'text'}
{selection_text[:200]}{'...' if len(selection_text) > 200 else ''}
```

**Your question**: {user_message}

I can help you with:
• **Code analysis** - Understanding what this code does
• **Bug fixes** - Finding and fixing issues  
• **Refactoring** - Improving code structure
• **Documentation** - Adding comments and docs
• **Testing** - Writing unit tests

What would you like me to focus on?"""
        
        elif 'explain' in message or 'what does' in message:
            return f"""I can see you're working on **{file_name}** ({active_language}). 

To explain this code, I would need to:
1. **Analyze** the file structure and dependencies
2. **Understand** the code's purpose and flow  
3. **Identify** key functions and components
4. **Explain** in clear, simple terms

Since I can see you have this file open, I can provide more specific help if you select the code you want explained, or ask about specific functions or concepts!"""
        
        elif 'fix' in message or 'debug' in message or 'error' in message:
            return f"""I'm ready to help debug **{file_name}** ({active_language})!

**Debugging approach**:
1. **Identify** the error or issue  
2. **Analyze** the code context
3. **Check** for common patterns and anti-patterns
4. **Suggest** specific fixes with explanations

**What I can help with**:
• Syntax errors and typos
• Logic bugs and edge cases  
• Performance optimizations
• Best practices and code quality

Can you describe the specific issue you're encountering, or select the problematic code?"""
        
        else:
            return f"""I can see you're working on **{file_name}** ({active_language}) in your {workspace_root.get('name', 'workspace')}.

**Your question**: {user_message}

I'm ready to help with any coding tasks! I can:
• **Read and analyze** your code
• **Write new functions** and features  
• **Debug and fix** issues
• **Refactor and optimize** code
• **Generate tests** and documentation

What would you like to work on?"""
    
    # General responses for when no file is open
    if 'hello' in message or 'hi' in message:
        return f"""Hello! I'm NAVI, your autonomous engineering assistant. 

I can see you're in the **{workspace_root.get('name', 'workspace')}** workspace. I'm ready to help with:

• **Code development** - Writing, reviewing, and debugging
• **Project analysis** - Understanding codebases and architecture  
• **File operations** - Creating, reading, and modifying files
• **Terminal commands** - Running scripts and tools
• **Documentation** - Writing docs and comments

What can I help you build today?"""
    
    elif 'create' in message or 'make' in message or 'build' in message:
        return f"""I'd love to help you create something! 

**What I can build**:
• **New files** - Components, modules, configurations
• **Functions and classes** - Complete implementations
• **Tests** - Unit tests, integration tests  
• **Documentation** - READMEs, API docs
• **Scripts** - Automation and utility scripts

**To get started**:
1. Tell me what you want to create
2. I'll ask for any needed details  
3. I'll generate the code with explanations
4. We can iterate and improve together

What would you like to create?"""
    
    elif 'help' in message:
        return f"""I'm NAVI, your VS Code AI assistant! Here's what I can do:

**🔍 Code Analysis**
• Understand and explain code
• Find bugs and suggest fixes
• Review code quality and patterns

**✏️ Code Generation**  
• Write functions, classes, and modules
• Create tests and documentation
• Generate boilerplate and templates

**🛠 Development Tasks**
• Run terminal commands
• Modify files and project structure  
• Set up configurations and workflows

**💡 Smart Context**
I can see your current file, selected code, and workspace to provide targeted help.

Try asking me to:
• "Explain this function" (select code first)
• "Create a new component"  
• "Fix this bug"
• "Write tests for this code"

What can I help you with?"""
    
    else:
        # More varied responses based on message content
        if 'test' in message:
            return "I see you're testing! Everything looks good. Try asking me something more specific like 'explain this code' or 'help me debug an issue'."
        elif 'thanks' in message or 'thank you' in message:
            return "You're welcome! I'm here whenever you need help with coding, debugging, or building something new."
        elif any(greeting in message for greeting in ['how are you', 'what\'s up', 'how\'s it going']):
            return f"I'm doing great, thanks for asking! I'm ready to help you code. I can see you're in the **{workspace_root.get('name', 'current')}** workspace. What would you like to work on?"
        elif 'tell me about' in message or 'what is' in message:
            return f"Great question! For **{user_message}**, I'd be happy to explain. Can you be more specific about what aspect you'd like to know about? I can help with concepts, code examples, or practical implementations."
        else:
            return f"Interesting question: _{user_message}_\n\nI'm ready to help! Here are some things I'm great at:\n\n• **Code analysis** and explanation\n• **Debugging** and troubleshooting\n• **Writing new code** and features\n• **Refactoring** and optimization\n\nWhat specific coding task can I help you with?"

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "backend": "NAVI FastAPI Backend", 
        "version": "1.0.0",
        "features": ["streaming", "context_aware", "vs_code_integration"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8787)