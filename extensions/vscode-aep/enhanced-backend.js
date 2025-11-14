#!/usr/bin/env node
/**
 * Enhanced NAVI Backend with Rich Context Support
 * 
 * This backend now accepts rich payloads including:
 * - User message text
 * - Selected model and mode from UI
 * - Editor context (file, language, selection)
 * - Conversation history (TODO)
 * 
 * Usage:
 *   node enhanced-backend.js
 * 
 * Configure VS Code setting:
 *   "aep.naviBackendUrl": "http://127.0.0.1:8787/api/chat"
 */

const express = require('express');
const cors = require('cors');

// Processing time calculation constants
const MAX_PROCESSING_MS = 3000;    // Maximum response delay
const BASE_DELAY_MS = 800;         // Base processing time
const MS_PER_CHAR = 5;             // Additional delay per message character
const SELECTION_BONUS_MS = 500;    // Extra delay when user has code selected

const app = express();
const PORT = 8787;

// Simple message queue to serialize responses
let messageQueue = Promise.resolve();

// Middleware
app.use(cors());
app.use(express.json());

// Enhanced chat endpoint with rich context
app.post('/api/chat', (req, res) => {
    messageQueue = messageQueue.then(() =>
        new Promise(resolve => {
            const {
                message,
                model = 'Unknown',
                mode = 'Unknown',
                editor = {},
                conversationId = null,
                history = []
            } = req.body;

            console.log(`[Enhanced Backend] Received rich context:`);
            console.log(`  Message: "${message}"`);
            console.log(`  Model: ${model}`);
            console.log(`  Mode: ${mode}`);
            if (editor.fileName) {
                console.log(`  File: ${editor.fileName} (${editor.languageId})`);
                if (editor.selection) {
                    console.log(`  Selection: "${editor.selection.substring(0, 100)}${editor.selection.length > 100 ? '...' : ''}"`);
                }
            }

            // Generate context-aware responses
            let reply = generateContextualReply(message, model, mode, editor);

            const responseData = {
                reply,
                meta: {
                    model_used: model,
                    finish_reason: 'stop',
                    usage: {
                        input_tokens: Math.floor(message.length / 4), // rough estimate
                        output_tokens: Math.floor(reply.length / 4),
                        total_tokens: Math.floor((message.length + reply.length) / 4)
                    }
                }
            };

            // Simulate processing time based on content complexity
            const processingTime = Math.min(
                MAX_PROCESSING_MS, 
                BASE_DELAY_MS + (message.length * MS_PER_CHAR) + (editor.selection ? SELECTION_BONUS_MS : 0)
            );

            setTimeout(() => {
                res.json(responseData);
                resolve();
            }, processingTime);
        })
    );
});

function generateContextualReply(message, model, mode, editor) {
    const hasFile = editor.fileName && !editor.fileName.includes('Untitled');
    const hasSelection = editor.selection && editor.selection.trim().length > 0;
    const language = editor.languageId || 'unknown';

    // Context-aware response generation
    if (hasSelection && language) {
        if (message.toLowerCase().includes('explain') || message.toLowerCase().includes('what does')) {
            return `I can see you've selected ${editor.selection.split('\n').length} line(s) of ${language} code. Let me analyze it:\n\n\`\`\`${language}\n${editor.selection}\n\`\`\`\n\nThis appears to be ${language} code. While I'm in demo mode, a real AI backend would provide detailed code explanation, suggest improvements, or identify potential issues based on your "${message}" request.\n\n🧠 **Model**: ${model} | **Mode**: ${mode}`;
        }
        if (message.toLowerCase().includes('fix') || message.toLowerCase().includes('debug')) {
            return `I can help debug this ${language} code selection! In a real implementation, I would:\n\n1. **Analyze** the selected code for syntax errors\n2. **Check** for logical issues or anti-patterns  \n3. **Suggest** specific fixes with explanations\n4. **Generate** corrected code with diff highlighting\n\n\`\`\`${language}\n${editor.selection}\n\`\`\`\n\n🔧 Ready to connect real debugging capabilities!\n\n🧠 **Model**: ${model} | **Mode**: ${mode}`;
        }
        if (message.toLowerCase().includes('test') || message.toLowerCase().includes('unit')) {
            return `Perfect! I can see ${language} code that needs test coverage. A production AI would:\n\n✅ Generate comprehensive unit tests\n✅ Mock external dependencies  \n✅ Cover edge cases and error scenarios\n✅ Follow ${language} testing best practices\n\nFor this selection:\n\`\`\`${language}\n${editor.selection.substring(0, 200)}${editor.selection.length > 200 ? '...' : ''}\n\`\`\`\n\n🧪 Ready to write real tests!\n\n🧠 **Model**: ${model} | **Mode**: ${mode}`;
        }
    }

    if (hasFile) {
        const fileName = editor.fileName.split('/').pop() || editor.fileName;
        if (message.toLowerCase().includes('file') || message.toLowerCase().includes('document')) {
            return `I can see you're working on **${fileName}** (${language}). In full mode, I would:\n\n📁 **File Analysis**: Read entire file structure\n🔍 **Dependencies**: Analyze imports and relationships\n📝 **Documentation**: Generate/improve comments and docs\n🔧 **Refactoring**: Suggest architectural improvements\n\n${hasSelection ? '**Selected text**: ' + editor.selection.substring(0, 100) + (editor.selection.length > 100 ? '...' : '') : '**Full file context** available'}\n\n🧠 **Model**: ${model} | **Mode**: ${mode}`;
        }
    }

    // Mode-specific responses
    if (mode.toLowerCase().includes('agent')) {
        return `🤖 **Agent Mode Active**: I have full access to your workspace and can:\n\n• **Read/Write Files**: Create, modify, delete any project files\n• **Run Commands**: Execute terminal commands and scripts  \n• **Code Generation**: Write complete functions, classes, modules\n• **Project Analysis**: Understand entire codebase structure\n• **Debugging**: Find and fix issues across multiple files\n\nYour message: "${message}"\n\n${hasFile ? `Current context: ${editor.fileName} (${language})` : 'Ready to assist with any coding task!'}\n\n🧠 **Model**: ${model}`;
    }

    if (mode.toLowerCase().includes('chat')) {
        return `💬 **Chat Mode**: I can help answer questions and provide guidance, but I'm limited to read-only access.\n\nYour question: "${message}"\n\n${hasFile ? `I can see you're in ${editor.fileName}, which looks like ${language} code. ` : ''}I can provide explanations, suggestions, and code examples, but I cannot modify files directly.\n\n🧠 **Model**: ${model}`;
    }

    // Model-specific responses  
    const modelResponses = {
        'ChatGPT 5.1': `🚀 **ChatGPT 5.1**: Advanced reasoning and code understanding active. Your message "${message}" received with full context awareness.`,
        'Claude 3.5 Sonnet': `🎵 **Claude 3.5 Sonnet**: Excellent code analysis and creative problem-solving ready. Processing "${message}" with contextual intelligence.`,
        'GPT-4 Turbo': `⚡ **GPT-4 Turbo**: Fast, efficient responses with deep technical knowledge. Analyzing "${message}" in current context.`,
        'Local LLM': `🏠 **Local LLM**: Privacy-focused local processing active. Your "${message}" stays on your machine.`
    };

    const modelResponse = modelResponses[model] || `🤖 **${model}**: Processing your request "${message}".`;

    // Default contextual response
    return `${modelResponse}\n\n${hasFile ? `📁 **Context**: ${editor.fileName} (${language})\n` : ''}${hasSelection ? `📝 **Selection**: ${editor.selection.length} characters selected\n` : ''}🎯 **Mode**: ${mode}\n\nThis is a demo response showing rich context integration. A real backend would provide intelligent, context-aware assistance based on your specific request and current workspace state!\n\n🔌 **Ready for**: OpenAI GPT-4, Anthropic Claude, local LLMs, or custom AI services.`;
}

// Health check endpoint
app.get('/api/health', (req, res) => {
    res.json({
        status: 'healthy',
        backend: 'Enhanced NAVI Backend',
        version: '2.0.0',
        features: ['rich_context', 'editor_integration', 'streaming_ready'],
        timestamp: new Date().toISOString()
    });
});

// Start server
app.listen(PORT, () => {
    console.log(`🦊 Enhanced NAVI Backend running at http://127.0.0.1:${PORT}`);
    console.log(`💬 Chat endpoint: POST http://127.0.0.1:${PORT}/api/chat`);
    console.log(`🔍 Health check: GET http://127.0.0.1:${PORT}/api/health`);
    console.log(`\n📋 VS Code Configuration:`);
    console.log(`   "aep.naviBackendUrl": "http://127.0.0.1:${PORT}/api/chat"`);
    console.log(`\n✨ New Features:`);
    console.log(`   • Rich context payloads (editor, model, mode)`);
    console.log(`   • Code-aware responses`);
    console.log(`   • Context-sensitive assistance`);
    console.log(`   • Streaming infrastructure ready`);
    console.log(`\n🛑 Press Ctrl+C to stop`);
});