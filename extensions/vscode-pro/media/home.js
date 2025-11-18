// AEP Professional Webview Script
(function () {
    const vscode = acquireVsCodeApi();

    // DOM elements
    const signinBtn = document.getElementById('signinBtn');
    const modelBtn = document.getElementById('modelBtn');
    const settingsBtn = document.getElementById('settingsBtn');
    const chatSend = document.getElementById('chatSend');
    const chatInput = document.getElementById('chatInput');
    const chatLog = document.getElementById('chatLog');
    const heroSection = document.getElementById('hero');

    // State
    let isSignedIn = false;
    let currentModel = 'gpt-4o';

    // Initialize
    init();

    function init() {
        setupEventListeners();
        vscode.postMessage({ type: 'ready' });
    }

    function setupEventListeners() {
        // Button click handlers
        signinBtn?.addEventListener('click', handleSignIn);
        modelBtn?.addEventListener('click', handleModelSelect);
        settingsBtn?.addEventListener('click', handleSettings);
        chatSend?.addEventListener('click', handleSend);

        // Chat input handlers
        chatInput?.addEventListener('keydown', handleInputKeydown);
        chatInput?.addEventListener('input', handleInputChange);

        // Action button handlers
        document.addEventListener('click', handleActionClick);

        // Window message handler
        window.addEventListener('message', handleMessage);
    }

    function handleSignIn() {
        if (isSignedIn) {
            vscode.postMessage({ type: 'signout' });
        } else {
            vscode.postMessage({ type: 'signin' });
        }
    }

    function handleModelSelect() {
        vscode.postMessage({ type: 'model:select' });
    }

    function handleSettings() {
        vscode.postMessage({ type: 'settings' });
    }

    function handleSend() {
        const text = chatInput?.value?.trim();
        if (!text) return;

        if (!isSignedIn) {
            showError('Please sign in first to chat with AEP Professional.');
            return;
        }

        appendMessage('user', text);
        chatInput.value = '';
        updateSendButton();
        hideHero();
        showThinking();

        vscode.postMessage({ type: 'chat:send', text });
    }

    function handleInputKeydown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    }

    function handleInputChange(e) {
        // Auto-resize textarea
        e.target.style.height = 'auto';
        e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
        updateSendButton();
    }

    function handleActionClick(e) {
        const actionBtn = e.target.closest('[data-action]');
        if (actionBtn) {
            const action = actionBtn.getAttribute('data-action');
            vscode.postMessage({ type: 'action', action });
        }
    }

    function handleMessage(event) {
        const { type, payload, text, error } = event.data || {};

        switch (type) {
            case 'state':
                updateState(payload);
                break;
            case 'chat:reply':
                hideThinking();
                appendMessage('assistant', text);
                break;
            case 'chat:error':
                hideThinking();
                showError(error);
                break;
            case 'chat:prefill':
                chatInput.value = text;
                chatInput.focus();
                updateSendButton();
                hideHero();
                break;
            case 'error':
                hideThinking();
                showError(error);
                break;
            default:
                console.log('Unknown message type:', type);
        }
    }

    function updateState(state) {
        isSignedIn = state.signedIn;
        currentModel = state.model;

        // Update sign in button
        if (signinBtn) {
            signinBtn.textContent = isSignedIn ? 'Sign out' : 'Sign in';
            signinBtn.className = isSignedIn ? 'secondary' : 'primary';
        }

        // Update model button
        if (modelBtn) {
            modelBtn.textContent = `Model: ${currentModel}`;
        }

        // Update UI state
        updateSendButton();
    }

    function updateSendButton() {
        if (chatSend && chatInput) {
            const hasText = chatInput.value.trim().length > 0;
            chatSend.disabled = !hasText || !isSignedIn;
        }
    }

    function appendMessage(role, content) {
        if (!chatLog) return;

        const messageEl = document.createElement('div');
        messageEl.className = `message ${role}`;

        const contentEl = document.createElement('div');
        contentEl.className = 'content';

        if (role === 'assistant') {
            contentEl.innerHTML = formatContent(content);
        } else {
            contentEl.textContent = content;
        }

        messageEl.appendChild(contentEl);
        chatLog.appendChild(messageEl);

        // Scroll to bottom
        chatLog.scrollTop = chatLog.scrollHeight;
    }

    function formatContent(content) {
        // Basic markdown-like formatting
        return content
            .replace(/```([\\w]*)\n([\\s\\S]*?)```/g, (match, lang, code) => {
                return `<div class="code-block">
                    <div class="code-header">
                        <span>${lang || 'Code'}</span>
                        <button class="copy-btn" onclick="copyCode(this)">Copy</button>
                    </div>
                    <pre class="code-content"><code>${escapeHtml(code.trim())}</code></pre>
                </div>`;
            })
            .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
            .replace(/\n/g, '<br>');
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Global function for code copying (called from formatted HTML)
    window.copyCode = function (btn) {
        const codeContent = btn.closest('.code-block').querySelector('.code-content').textContent;
        navigator.clipboard.writeText(codeContent).then(() => {
            const originalText = btn.textContent;
            btn.textContent = 'Copied!';
            setTimeout(() => {
                btn.textContent = originalText;
            }, 2000);
        });
    };

    function showThinking() {
        appendMessage('assistant', '<div class="thinking">🤔 Thinking...</div>');
    }

    function hideThinking() {
        const thinkingMsg = chatLog?.querySelector('.message:last-child .thinking');
        if (thinkingMsg) {
            thinkingMsg.closest('.message').remove();
        }
    }

    function showError(message) {
        appendMessage('assistant', `❌ ${message}`);
    }

    function hideHero() {
        if (heroSection) {
            heroSection.style.display = 'none';
        }
    }

})();