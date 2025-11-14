#!/usr/bin/env node
/**
 * Quick Demo Backend for NAVI Extension Testing
 * 
 * ⚠️  **WARNING: NOT PRODUCTION READY** ⚠️
 * This is a DEMO server with NO security features:
 * - No authentication or authorization
 * - No rate limiting or request validation  
 * - No input sanitization or output filtering
 * - No HTTPS/TLS encryption
 * - Accepts all CORS origins (*)
 * 
 * ❌ DO NOT expose this server to the internet
 * ❌ DO NOT use in production environments
 * ✅ Local development and testing ONLY
 * 
 * This is a simple Express.js server that provides a /api/chat endpoint
 * for testing the NAVI VS Code extension's HTTP integration.
 * 
 * Usage:
 *   node demo-backend.js
 * 
 * Then configure VS Code setting:
 *   "aep.naviBackendUrl": "http://localhost:8000/api/chat"
 */

const express = require('express');
const cors = require('cors');

const app = express();
const PORT = 8000;

// Simple message queue to serialize /api/chat responses and prevent out-of-order delivery
let messageQueue = Promise.resolve();

// Middleware
app.use(cors());
app.use(express.json());

// Simple chat endpoint for testing
app.post('/api/chat', (req, res) => {
    messageQueue = messageQueue.then(() =>
        new Promise(resolve => {
            const { message } = req.body;

            console.log(`[Demo Backend] Received: ${message}`);

            // Simple demo responses
            const responses = [
                `Hello! I received your message: "${message}". I'm a demo backend server running on Node.js + Express.`,
                `Thanks for testing NAVI! Your message was: "${message}". 🦊 The backend integration is working perfectly!`,
                `I heard you say: "${message}". This is just a demo server - connect your real AI backend here! ✨`,
                `Message processed: "${message}". Ready to connect to real AI services like OpenAI, Claude, or local LLMs! 🚀`,
            ];

            const reply = responses[Math.floor(Math.random() * responses.length)];

            // Simulate some processing time
            setTimeout(() => {
                res.json({ reply });
                resolve();
            }, 800 + Math.random() * 1200); // 0.8-2s delay
        })
    );
});

// Health check endpoint
app.get('/api/health', (req, res) => {
    res.json({ status: 'healthy', backend: 'NAVI Demo Server', timestamp: new Date().toISOString() });
});

// Start server
app.listen(PORT, () => {
    console.log(`🦊 NAVI Demo Backend running at http://localhost:${PORT}`);
    console.log(`💬 Chat endpoint: POST http://localhost:${PORT}/api/chat`);
    console.log(`🔍 Health check: GET http://localhost:${PORT}/api/health`);

    console.log(`\n⚠️  SECURITY WARNING: DEMO ONLY - NOT PRODUCTION READY`);
    console.log(`   • No authentication, rate limiting, or input validation`);
    console.log(`   • Do NOT expose to internet or production environments`);
    console.log(`   • Local development testing ONLY`);

    console.log(`\n📋 VS Code Configuration:`);
    console.log(`   "aep.naviBackendUrl": "http://localhost:${PORT}/api/chat"`);
    console.log(`\n🛑 Press Ctrl+C to stop`);
});