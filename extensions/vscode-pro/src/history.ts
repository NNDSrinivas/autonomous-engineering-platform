import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

export type AepMessage = {
    role: 'user' | 'assistant' | 'system';
    text: string;
    ts: number;
};

export type AepSession = {
    id: string;
    title: string;
    messages: AepMessage[];
    updatedAt: number;
};

export class HistoryStore {
    private file: string;

    constructor(private context: vscode.ExtensionContext) {
        // Use globalStorageUri for persistent storage across workspaces
        const storageDir = this.context.globalStorageUri.fsPath;
        this.file = path.join(storageDir, 'aep-history.json');
    }

    private ensureDir(): void {
        const dir = path.dirname(this.file);
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }
    }

    private read(): AepSession[] {
        try {
            if (fs.existsSync(this.file)) {
                const content = fs.readFileSync(this.file, 'utf8');
                return JSON.parse(content);
            }
        } catch (error) {
            console.error('Failed to read history file:', error);
        }
        return [];
    }

    private write(data: AepSession[]): void {
        try {
            this.ensureDir();
            fs.writeFileSync(this.file, JSON.stringify(data, null, 2));
        } catch (error) {
            console.error('Failed to write history file:', error);
        }
    }

    list(): AepSession[] {
        return this.read().sort((a, b) => b.updatedAt - a.updatedAt);
    }

    getSession(sessionId: string): AepSession | undefined {
        const all = this.read();
        return all.find(s => s.id === sessionId);
    }

    upsertMessage(sessionId: string, msg: AepMessage, title?: string): void {
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

    createSession(title?: string): AepSession {
        const id = this.generateSessionId();
        const session: AepSession = {
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

    deleteSession(sessionId: string): boolean {
        const all = this.read();
        const index = all.findIndex(s => s.id === sessionId);

        if (index !== -1) {
            all.splice(index, 1);
            this.write(all);
            return true;
        }

        return false;
    }

    clearAll(): void {
        this.write([]);
    }

    private generateSessionId(): string {
        return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    // Utility to generate a readable title from the first user message
    generateTitleFromMessage(message: string): string {
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