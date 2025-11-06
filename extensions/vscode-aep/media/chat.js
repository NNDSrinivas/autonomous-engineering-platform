const vscode = acquireVsCodeApi();

window.addEventListener('DOMContentLoaded', () => {
  // Sign in button
  document.getElementById('signIn')?.addEventListener('click', ()=> {
    console.log('Sign In clicked');
    vscode.postMessage({ type:'signIn' });
  });
  
  // Open portal button  
  document.getElementById('openPortal')?.addEventListener('click', ()=> {
    console.log('Open Portal clicked');
    vscode.postMessage({ type:'openPortal' });
  });
  
  // Start session button
  document.getElementById('start')?.addEventListener('click', ()=> {
    console.log('Start Session clicked');
    vscode.postMessage({ type:'startSession' });
  });
  
  // Refresh button
  document.getElementById('refresh')?.addEventListener('click', ()=> {
    console.log('Refresh clicked');
    vscode.postMessage({ type:'refresh' });
  });
  
  // Send chat button
  document.getElementById('sendChat')?.addEventListener('click', ()=> {
    const input = document.getElementById('chatInput');
    const message = input?.value?.trim();
    if (message) {
      console.log('Chat message:', message);
      vscode.postMessage({ type:'chat', message });
      input.value = '';
    }
  });
  
  // Enter key in chat input
  document.getElementById('chatInput')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      document.getElementById('sendChat')?.click();
    }
  });
  
  // Demo chat functionality
  document.getElementById('demoSend')?.addEventListener('click', () => {
    const input = document.getElementById('demoInput');
    const message = input?.value?.trim();
    if (message) {
      addDemoMessage(message, 'user');
      input.value = '';
      
      // Simulate AI response
      setTimeout(() => {
        const responses = [
          "I'd be happy to help you with that! Could you share more details about your project structure?",
          "Let me analyze your code. I can help with refactoring, bug fixes, or implementing new features.",
          "Great question! I can assist with code reviews, testing strategies, and best practices.",
          "I'm here to help! Whether it's debugging, optimization, or architecture advice, just let me know."
        ];
        const response = responses[Math.floor(Math.random() * responses.length)];
        addDemoMessage(response, 'assistant');
      }, 1000);
    }
  });
  
  // Enter key in demo input
  document.getElementById('demoInput')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      document.getElementById('demoSend')?.click();
    }
  });
  
  // Get Started button (primary CTA)
  document.getElementById('getStarted')?.addEventListener('click', () => {
    console.log('Get Started clicked');
    vscode.postMessage({ type: 'signIn' });
  });
  
  // Sign In button (secondary action)  
  document.getElementById('signIn')?.addEventListener('click', () => {
    console.log('Sign In clicked');
    vscode.postMessage({ type: 'signIn' });
  });
  
  // External links
  document.querySelectorAll('[data-url]')?.forEach(a=> a.addEventListener('click', (e)=>{ 
    e.preventDefault(); 
    console.log('External link clicked:', a.getAttribute('data-url'));
    vscode.postMessage({ type:'openExternal', url: a.getAttribute('data-url') }); 
  }));
  
  // Issue selection buttons
  document.querySelectorAll('vscode-button[data-key]')?.forEach(b=> b.addEventListener('click', ()=> {
    console.log('Issue selected:', b.getAttribute('data-key'));
    vscode.postMessage({ type:'pickIssue', key: b.getAttribute('data-key') });
  }));
});

// Listen for messages from extension
window.addEventListener('message', event => {
  const message = event.data;
  
  if (message.type === 'chatMessage') {
    addChatMessage(message.role, message.content, message.timestamp);
  }
});

function addDemoMessage(message, sender) {
  const demoMessages = document.getElementById('demoMessages');
  if (demoMessages) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `demo-message ${sender}`;
    messageDiv.textContent = message;
    demoMessages.appendChild(messageDiv);
    demoMessages.scrollTop = demoMessages.scrollHeight;
  }
}

function addChatMessage(role, content, timestamp) {
  // Find or create chat messages container
  let chatContainer = document.getElementById('chatMessages');
  if (!chatContainer) {
    // Create chat messages area if it doesn't exist
    const chatCard = document.querySelector('.card:has(#chatInput)')?.parentNode;
    if (chatCard) {
      chatContainer = document.createElement('div');
      chatContainer.id = 'chatMessages';
      chatContainer.style.cssText = 'max-height: 300px; overflow-y: auto; margin: 8px 0; padding: 8px; border: 1px solid var(--vscode-editorWidget-border); background: var(--vscode-editor-background);';
      chatCard.insertBefore(chatContainer, chatCard.querySelector('#chatInput'));
    }
  }
  
  if (chatContainer) {
    const messageDiv = document.createElement('div');
    messageDiv.style.cssText = `margin: 4px 0; padding: 8px; border-radius: 4px; ${
      role === 'user' 
        ? 'background: var(--vscode-button-background); color: var(--vscode-button-foreground); text-align: right;'
        : role === 'assistant'
        ? 'background: var(--vscode-textBlockQuote-background); color: var(--vscode-foreground);'
        : 'background: var(--vscode-badge-background); color: var(--vscode-badge-foreground); font-style: italic;'
    }`;
    
    // Create metadata div
    const metaDiv = document.createElement('div');
    metaDiv.style.cssText = "font-size: 0.9em; opacity: 0.7; margin-bottom: 4px;";
    metaDiv.textContent =
      (role === 'user'
        ? '👤 You'
        : role === 'assistant'
        ? '🤖 AEP Agent'
        : '💭 System')
      + ' • ' + timestamp;
    
    // Create content div (sanitize user content via textContent)
    const contentDiv = document.createElement('div');
    contentDiv.textContent = content;
    
    messageDiv.appendChild(metaDiv);
    messageDiv.appendChild(contentDiv);

    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }
}