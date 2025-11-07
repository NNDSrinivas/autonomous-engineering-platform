#!/usr/bin/env node

// Simple test server for VS Code extension development
const http = require('http');
const url = require('url');

const server = http.createServer((req, res) => {
  const parsedUrl = url.parse(req.url, true);
  const path = parsedUrl.pathname;
  
  // Set CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  res.setHeader('Content-Type', 'application/json');

  // Handle preflight requests
  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }

  console.log(`${req.method} ${path}`);

  // Health check
  if (path === '/api/health') {
    res.writeHead(200);
    res.end(JSON.stringify({ status: 'ok', message: 'Test server running' }));
    return;
  }

  // User info
  if (path === '/api/user/me') {
    res.writeHead(200);
    res.end(JSON.stringify({ 
      id: 'user123',
      name: 'Alex Developer', 
      username: 'alex.dev',
      email: 'alex@example.com'
    }));
    return;
  }

  // JIRA tasks
  if (path === '/api/jira/tasks') {
    res.writeHead(200);
    res.end(JSON.stringify({
      tasks: [
        {
          id: 'DEMO-123',
          key: 'DEMO-123',
          summary: 'Implement user authentication system',
          status: 'In Progress',
          url: 'https://demo.atlassian.net/browse/DEMO-123',
          priority: 'High'
        },
        {
          id: 'DEMO-124',
          key: 'DEMO-124',
          summary: 'Add responsive design to dashboard',
          status: 'To Do',
          url: 'https://demo.atlassian.net/browse/DEMO-124',
          priority: 'Medium'
        }
      ],
      total: 2
    }));
    return;
  }

  // Chat endpoint
  if (path === '/api/chat' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        const data = JSON.parse(body);
        const userMessage = data.message || '';
        
        // Simple response based on message content
        let response = '';
        if (userMessage.toLowerCase().includes('hello') || userMessage.toLowerCase().includes('hi')) {
          response = '👋 Hello! I\'m your AEP Agent. I can help you with code analysis, project planning, and JIRA task management. How can I assist you today?';
        } else if (userMessage.toLowerCase().includes('help')) {
          response = '🚀 Here\'s what I can help you with:\n\n• **Code Analysis**: Ask me to review your code\n• **Project Planning**: I can break down tasks into steps\n• **JIRA Integration**: Manage and plan your issues\n• **AI Assistance**: Get coding suggestions and solutions\n\nJust ask me anything!';
        } else if (userMessage.toLowerCase().includes('code') || userMessage.toLowerCase().includes('function')) {
          response = '💻 I\'d be happy to help with your code! I can:\n\n• Review and analyze existing code\n• Suggest improvements and optimizations\n• Help debug issues\n• Generate new functions or components\n\nPlease share your code or describe what you\'re working on!';
        } else {
          response = `🤔 I understand you said: "${userMessage}"\n\nI'm here to help with your development tasks! Try asking me about:\n• Code review and analysis\n• Project planning\n• JIRA task management\n• Technical questions\n\nWhat would you like to work on?`;
        }

        res.writeHead(200);
        res.end(JSON.stringify({
          response: response,
          timestamp: new Date().toISOString()
        }));
      } catch (error) {
        res.writeHead(400);
        res.end(JSON.stringify({ error: 'Invalid JSON' }));
      }
    });
    return;
  }

  // Device code flow (mock OAuth)
  if (path === '/api/oauth/device/code') {
    res.writeHead(200);
    res.end(JSON.stringify({
      device_code: 'demo_device_' + Date.now(),
      user_code: 'ABCD-1234',
      verification_uri: 'https://portal.aep.navra.ai/device',
      verification_uri_complete: 'https://portal.aep.navra.ai/device?code=ABCD-1234',
      expires_in: 900
    }));
    return;
  }

  if (path === '/api/oauth/device/token') {
    res.writeHead(200);
    res.end(JSON.stringify({
      access_token: 'demo_token_' + Date.now(),
      token_type: 'Bearer',
      expires_in: 3600
    }));
    return;
  }

  // Default 404
  res.writeHead(404);
  res.end(JSON.stringify({ error: 'Not found' }));
});

const PORT = 8001;
server.listen(PORT, () => {
  console.log(`🚀 AEP Test Server running on http://localhost:${PORT}`);
  console.log('📋 Available endpoints:');
  console.log('  GET  /api/health - Health check');
  console.log('  GET  /api/user/me - User info');
  console.log('  GET  /api/jira/tasks - JIRA tasks');
  console.log('  POST /api/chat - Chat with AI');
  console.log('  POST /api/oauth/device/code - Device code flow');
  console.log('  POST /api/oauth/device/token - Get access token');
  console.log('\n💡 Configure VS Code extension with:');
  console.log('  aep.baseUrl: http://localhost:8001');
});