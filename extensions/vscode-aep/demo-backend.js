#!/usr/bin/env node
/**
 * Quick Demo Backend for NAVI Extension Testing
 * 
 * This is a simple Express.js server that provides a /api/chat endpoint
 * for testing the NAVI VS Code extension's HTTP integration.
 * 
 * Usage:
 *   node demo-backend.js
 * 
 * Then configure VS Code setting:
 *   "aep.naviBackendUrl": "http://localhost:8000"
 */

const express = require('express');
const cors = require('cors');

const app = express();
const PORT = 8000;

// Middleware
app.use(cors());
app.use(express.json());

// Simple chat endpoint for testing
app.post('/api/chat', (req, res) => {
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
    }, 800 + Math.random() * 1200); // 0.8-2s delay
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
    console.log(`\n📋 VS Code Configuration:`);
    console.log(`   "aep.naviBackendUrl": "http://localhost:${PORT}"`);
    console.log(`\n🛑 Press Ctrl+C to stop`);
});