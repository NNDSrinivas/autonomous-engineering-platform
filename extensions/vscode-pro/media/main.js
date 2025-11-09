// media/main.js
const vscode = acquireVsCodeApi();

const dom = {
    authBtn: document.getElementById('authBtn'),
    modelSelect: document.getElementById('modelSelect'),
    mcpList: document.getElementById('mcpList'),
    chatLog: document.getElementById('chatLog'),
    chatInput: document.getElementById('chatInput'),
    sendBtn: document.getElementById('sendBtn'),
    clearBtn: document.getElementById('clearBtn'),
};

function post(type, payload) { vscode.postMessage({ type, ...payload && { ...payload } }); }

window.addEventListener('message', (ev) => {
    const { type, payload } = ev.data || {};
    switch (type) {
        case 'state': {
            const { model, mcpServers, signedIn, accountName } = payload;
            if (model && dom.modelSelect.value !== model) {
                const opt = [...dom.modelSelect.options].find(o => o.text === model);
                if (opt) dom.modelSelect.value = opt.text; else dom.modelSelect.value = model;
            }
            renderMcp(mcpServers);
            dom.authBtn.textContent = signedIn ? (accountName ? `Signed in · ${accountName}` : 'Signed in') : 'Sign in';
            dom.authBtn.dataset.command = signedIn ? 'aep.signOut' : 'aep.signIn';
            break;
        }
        case 'chatAppend': {
            appendMsg(payload.role, payload.text);
            break;
        }
        default: break;
    }
});

function renderMcp(list = []) {
    dom.mcpList.innerHTML = '';
    if (!list.length) {
        const li = document.createElement('li');
        li.textContent = 'No servers configured';
        li.style.opacity = .7;
        dom.mcpList.appendChild(li);
        return;
    }
    list.forEach((s) => {
        const li = document.createElement('li');
        li.textContent = `${s.name} — ${s.url}`;
        dom.mcpList.appendChild(li);
    });
}

function appendMsg(role, text) {
    const el = document.createElement('div');
    el.className = 'msg';
    el.innerHTML = `<span class="role">${role}:</span><span class="text"></span>`;
    el.querySelector('.text').textContent = text;
    dom.chatLog.appendChild(el);
    dom.chatLog.scrollTop = dom.chatLog.scrollHeight;
}

dom.sendBtn.addEventListener('click', () => {
    const text = dom.chatInput.value.trim();
    if (!text) return;
    post('sendChat', { text });
    dom.chatInput.value = '';
});
dom.clearBtn.addEventListener('click', () => { dom.chatLog.innerHTML = ''; });

dom.modelSelect.addEventListener('change', () => {
    post('changeModel', { model: dom.modelSelect.value });
});

// Command buttons
document.querySelectorAll('[data-command]').forEach(btn => {
    btn.addEventListener('click', () => {
        const cmd = btn.getAttribute('data-command');
        if (!cmd) return;
        if (cmd === 'aep.signIn' || cmd === 'aep.signOut') {
            post(cmd === 'aep.signIn' ? 'signIn' : 'signOut');
        } else if (cmd === 'aep.addMcp') {
            post('addMcp');
        } else if (cmd === 'aep.openSettings') {
            post('openSettings');
        } else {
            // let extension run quick actions / etc.
            vscode.postMessage({ type: 'command', id: cmd });
        }
    });
});

// "Tabs" (no-op placeholders)
document.querySelectorAll('[data-action^="tab:"]').forEach(el => {
    el.addEventListener('click', () => {
        // You can route to dedicated sections here if needed
    });
});

post('ready');