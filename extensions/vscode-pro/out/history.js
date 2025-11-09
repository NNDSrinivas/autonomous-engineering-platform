"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.HistoryStore = void 0;
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
class HistoryStore {
    constructor(context) {
        this.context = context;
        // Use globalStorageUri for persistent storage across workspaces
        const storageDir = this.context.globalStorageUri.fsPath;
        this.file = path.join(storageDir, 'aep-history.json');
    }
    ensureDir() {
        const dir = path.dirname(this.file);
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }
    }
    read() {
        try {
            if (fs.existsSync(this.file)) {
                const content = fs.readFileSync(this.file, 'utf8');
                return JSON.parse(content);
            }
        }
        catch (error) {
            console.error('Failed to read history file:', error);
        }
        return [];
    }
    write(data) {
        try {
            this.ensureDir();
            fs.writeFileSync(this.file, JSON.stringify(data, null, 2));
        }
        catch (error) {
            console.error('Failed to write history file:', error);
        }
    }
    list() {
        return this.read().sort((a, b) => b.updatedAt - a.updatedAt);
    }
    getSession(sessionId) {
        const all = this.read();
        return all.find(s => s.id === sessionId);
    }
    upsertMessage(sessionId, msg, title) {
        const all = this.read();
        let session = all.find(s => s.id === sessionId);
        if (!session) {
            session = {
                id: sessionId,
                title: title || 'New Chat',
                messages: [],
                updatedAt: 0
            };
            all.push(session);
        }
        session.messages.push(msg);
        session.updatedAt = Date.now();
        if (title) {
            session.title = title;
        }
        this.write(all);
    }
    createSession(title) {
        const id = this.generateSessionId();
        const session = {
            id,
            title: title || 'New Chat',
            messages: [],
            updatedAt: Date.now()
        };
        const all = this.read();
        all.push(session);
        this.write(all);
        return session;
    }
    deleteSession(sessionId) {
        const all = this.read();
        const index = all.findIndex(s => s.id === sessionId);
        if (index !== -1) {
            all.splice(index, 1);
            this.write(all);
            return true;
        }
        return false;
    }
    clearAll() {
        this.write([]);
    }
    generateSessionId() {
        return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    // Utility to generate a readable title from the first user message
    generateTitleFromMessage(message) {
        const clean = message.trim();
        if (clean.length <= 50) {
            return clean;
        }
        // Find a good break point
        const truncated = clean.substring(0, 47);
        const lastSpace = truncated.lastIndexOf(' ');
        if (lastSpace > 20) {
            return truncated.substring(0, lastSpace) + '...';
        }
        return truncated + '...';
    }
}
exports.HistoryStore = HistoryStore;
//# sourceMappingURL=history.js.map