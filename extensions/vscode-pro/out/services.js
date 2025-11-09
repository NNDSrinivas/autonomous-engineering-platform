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
exports.GithubClient = exports.JiraClient = void 0;
const vscode = __importStar(require("vscode"));
class JiraClient {
    constructor(context) {
        this.context = context;
    }
    async connected() {
        try {
            const token = await this.getToken();
            return !!token;
        }
        catch {
            return false;
        }
    }
    async getToken() {
        // Try OAuth token first
        const raw = await this.context.secrets.get('aep.jira.oauth');
        if (raw) {
            try {
                const tokenData = JSON.parse(raw);
                if (Date.now() < tokenData.expires_at - 60000) {
                    return tokenData.access_token;
                }
            }
            catch {
                // Fall through to fallback
            }
        }
        // Fallback to basic auth with API token
        const cfg = vscode.workspace.getConfiguration('aep');
        const baseUrl = cfg.get('jira.baseUrl');
        const email = cfg.get('jira.email');
        const apiToken = cfg.get('jira.apiToken');
        if (baseUrl && email && apiToken) {
            return Buffer.from(`${email}:${apiToken}`).toString('base64');
        }
        return undefined;
    }
    async myAssigned(limit = 5) {
        const token = await this.getToken();
        if (!token)
            return [];
        try {
            // Check if it's OAuth token or basic auth
            const isOAuth = !token.includes(':');
            if (isOAuth) {
                // OAuth flow - use Atlassian gateway
                return await this.fetchWithOAuth(token, limit);
            }
            else {
                // Basic auth flow - use direct instance
                return await this.fetchWithBasicAuth(token, limit);
            }
        }
        catch (error) {
            console.error('Failed to fetch Jira issues:', error);
            return [];
        }
    }
    async fetchWithOAuth(token, limit) {
        try {
            // Get accessible resources first
            const resResp = await fetch('https://api.atlassian.com/oauth/token/accessible-resources', {
                headers: {
                    Authorization: `Bearer ${token}`,
                    'Accept': 'application/json'
                }
            });
            if (!resResp.ok)
                return [];
            const resources = await resResp.json();
            const site = resources?.find((r) => r.scopes?.includes('read:jira-work'));
            if (!site)
                return [];
            const jql = encodeURIComponent('assignee = currentUser() AND resolution = EMPTY ORDER BY updated DESC');
            const url = `https://api.atlassian.com/ex/jira/${site.id}/rest/api/3/search?jql=${jql}&maxResults=${limit}&fields=summary,status`;
            const resp = await fetch(url, {
                headers: {
                    Authorization: `Bearer ${token}`,
                    'Accept': 'application/json'
                }
            });
            if (!resp.ok)
                return [];
            const data = await resp.json();
            const issues = data?.issues || [];
            return issues.map((i) => ({
                key: i.key,
                summary: i.fields?.summary || '',
                url: `https://${site.url}/browse/${i.key}`,
                status: i.fields?.status?.name
            }));
        }
        catch (error) {
            console.error('OAuth fetch error:', error);
            return [];
        }
    }
    async fetchWithBasicAuth(token, limit) {
        try {
            const cfg = vscode.workspace.getConfiguration('aep');
            const baseUrl = cfg.get('jira.baseUrl');
            if (!baseUrl)
                return [];
            const jql = encodeURIComponent('assignee = currentUser() AND resolution = EMPTY ORDER BY updated DESC');
            const url = `${baseUrl}/rest/api/3/search?jql=${jql}&maxResults=${limit}&fields=summary,status`;
            const resp = await fetch(url, {
                headers: {
                    Authorization: `Basic ${token}`,
                    'Accept': 'application/json'
                }
            });
            if (!resp.ok)
                return [];
            const data = await resp.json();
            const issues = data?.issues || [];
            return issues.map((i) => ({
                key: i.key,
                summary: i.fields?.summary || '',
                url: `${baseUrl}/browse/${i.key}`,
                status: i.fields?.status?.name
            }));
        }
        catch (error) {
            console.error('Basic auth fetch error:', error);
            return [];
        }
    }
    async mySprint(limit = 5) {
        try {
            const token = await this.getToken();
            if (!token)
                return [];
            // Use OAuth method if available
            const raw = await this.context.secrets.get('aep.jira.oauth');
            if (raw) {
                return this.fetchSprintWithOAuth(token, limit);
            }
            else {
                return this.fetchSprintWithBasicAuth(token, limit);
            }
        }
        catch (error) {
            console.error('Failed to fetch sprint issues:', error);
            return [];
        }
    }
    async fetchSprintWithOAuth(token, limit) {
        try {
            // Get accessible resources first
            const resResp = await fetch('https://api.atlassian.com/oauth/token/accessible-resources', {
                headers: {
                    Authorization: `Bearer ${token}`,
                    'Accept': 'application/json'
                }
            });
            if (!resResp.ok)
                return [];
            const resources = await resResp.json();
            const site = resources?.find((r) => r.scopes?.includes('read:jira-work'));
            if (!site)
                return [];
            const jql = vscode.workspace.getConfiguration('aep').get('jira.sprintJql') ||
                'sprint in openSprints() AND assignee = currentUser() ORDER BY updated DESC';
            const encodedJql = encodeURIComponent(jql);
            const url = `https://api.atlassian.com/ex/jira/${site.id}/rest/api/3/search?jql=${encodedJql}&maxResults=${limit}&fields=summary,status`;
            const resp = await fetch(url, {
                headers: {
                    Authorization: `Bearer ${token}`,
                    'Accept': 'application/json'
                }
            });
            if (!resp.ok)
                return [];
            const data = await resp.json();
            const issues = data?.issues || [];
            return issues.map((i) => ({
                key: i.key,
                summary: i.fields?.summary || '',
                url: `https://${site.url}/browse/${i.key}`,
                status: i.fields?.status?.name
            }));
        }
        catch (error) {
            console.error('OAuth sprint fetch error:', error);
            return [];
        }
    }
    async fetchSprintWithBasicAuth(token, limit) {
        try {
            const cfg = vscode.workspace.getConfiguration('aep');
            const baseUrl = cfg.get('jira.baseUrl');
            const jql = cfg.get('jira.sprintJql') ||
                'sprint in openSprings() AND assignee = currentUser() ORDER BY updated DESC';
            const encodedJql = encodeURIComponent(jql);
            const url = `${baseUrl}/rest/api/3/search?jql=${encodedJql}&maxResults=${limit}&fields=summary,status`;
            const resp = await fetch(url, {
                headers: {
                    Authorization: `Basic ${token}`,
                    'Accept': 'application/json'
                }
            });
            if (!resp.ok)
                return [];
            const data = await resp.json();
            const issues = data?.issues || [];
            return issues.map((i) => ({
                key: i.key,
                summary: i.fields?.summary || '',
                url: `${baseUrl}/browse/${i.key}`,
                status: i.fields?.status?.name
            }));
        }
        catch (error) {
            console.error('Basic auth sprint fetch error:', error);
            return [];
        }
    }
}
exports.JiraClient = JiraClient;
class GithubClient {
    async connected() {
        try {
            const session = await vscode.authentication.getSession('github', ['read:user', 'repo'], { createIfNone: false });
            return !!session?.accessToken;
        }
        catch {
            return false;
        }
    }
    async getToken() {
        try {
            const session = await vscode.authentication.getSession('github', ['read:user', 'repo'], { createIfNone: false });
            return session?.accessToken;
        }
        catch {
            return undefined;
        }
    }
    async myOpenPRs(limit = 5) {
        const token = await this.getToken();
        if (!token)
            return [];
        try {
            // Get current user
            const userResp = await fetch('https://api.github.com/user', {
                headers: {
                    Authorization: `Bearer ${token}`,
                    'Accept': 'application/vnd.github+json'
                }
            });
            if (!userResp.ok)
                return [];
            const user = await userResp.json();
            const login = user?.login;
            if (!login)
                return [];
            // Search for open PRs by this user
            const query = encodeURIComponent(`is:pr is:open author:${login}`);
            const url = `https://api.github.com/search/issues?q=${query}&per_page=${limit}`;
            const resp = await fetch(url, {
                headers: {
                    Authorization: `Bearer ${token}`,
                    'Accept': 'application/vnd.github+json'
                }
            });
            if (!resp.ok)
                return [];
            const data = await resp.json();
            const items = data?.items || [];
            return items.map((i) => ({
                id: i.id,
                title: i.title,
                url: i.html_url,
                repo: (i.repository_url || '').split('/').slice(-2).join('/'),
                state: 'open'
            }));
        }
        catch (error) {
            console.error('Failed to fetch GitHub PRs:', error);
            return [];
        }
    }
    async prsNeedingMyReview(limit = 5) {
        const token = await this.getToken();
        if (!token)
            return [];
        try {
            // Get current user login
            const userResp = await fetch('https://api.github.com/user', {
                headers: {
                    Authorization: `Bearer ${token}`,
                    'Accept': 'application/vnd.github+json'
                }
            });
            if (!userResp.ok)
                return [];
            const user = await userResp.json();
            const login = user?.login;
            if (!login)
                return [];
            // Search for PRs requesting review from current user
            const query = `is:pr is:open review-requested:${login}`;
            const encodedQuery = encodeURIComponent(query);
            const url = `https://api.github.com/search/issues?q=${encodedQuery}&per_page=${limit}`;
            const resp = await fetch(url, {
                headers: {
                    Authorization: `Bearer ${token}`,
                    'Accept': 'application/vnd.github+json'
                }
            });
            if (!resp.ok)
                return [];
            const data = await resp.json();
            const items = data?.items || [];
            return items.map((i) => ({
                id: i.id,
                title: i.title,
                url: i.html_url,
                repo: (i.repository_url || '').split('/').slice(-2).join('/'),
                state: 'open'
            }));
        }
        catch (error) {
            console.error('Failed to fetch PRs needing review:', error);
            return [];
        }
    }
}
exports.GithubClient = GithubClient;
//# sourceMappingURL=services.js.map