import * as vscode from 'vscode';

export type JiraIssue = {
    key: string;
    summary: string;
    url: string;
    status?: string;
};

export type GhPr = {
    id: number;
    title: string;
    url: string;
    repo: string;
    state: string;
};

export class JiraClient {
    constructor(private context: vscode.ExtensionContext) { }

    async connected(): Promise<boolean> {
        try {
            const token = await this.getToken();
            return !!token;
        } catch {
            return false;
        }
    }

    private async getToken(): Promise<string | undefined> {
        // Try OAuth token first
        const raw = await this.context.secrets.get('aep.jira.oauth');
        if (raw) {
            try {
                const tokenData = JSON.parse(raw) as { access_token: string; expires_at: number };
                if (Date.now() < tokenData.expires_at - 60_000) {
                    return tokenData.access_token;
                }
            } catch {
                // Fall through to fallback
            }
        }

        // Fallback to basic auth with API token
        const cfg = vscode.workspace.getConfiguration('aep');
        const baseUrl = cfg.get<string>('jira.baseUrl');
        const email = cfg.get<string>('jira.email');
        const apiToken = cfg.get<string>('jira.apiToken');

        if (baseUrl && email && apiToken) {
            return Buffer.from(`${email}:${apiToken}`).toString('base64');
        }

        return undefined;
    }

    async myAssigned(limit = 5): Promise<JiraIssue[]> {
        const token = await this.getToken();
        if (!token) return [];

        try {
            // Check if it's OAuth token or basic auth
            const isOAuth = !token.includes(':');

            if (isOAuth) {
                // OAuth flow - use Atlassian gateway
                return await this.fetchWithOAuth(token, limit);
            } else {
                // Basic auth flow - use direct instance
                return await this.fetchWithBasicAuth(token, limit);
            }
        } catch (error) {
            console.error('Failed to fetch Jira issues:', error);
            return [];
        }
    }

    private async fetchWithOAuth(token: string, limit: number): Promise<JiraIssue[]> {
        try {
            // Get accessible resources first
            const resResp = await fetch('https://api.atlassian.com/oauth/token/accessible-resources', {
                headers: {
                    Authorization: `Bearer ${token}`,
                    'Accept': 'application/json'
                }
            });

            if (!resResp.ok) return [];

            const resources = await resResp.json() as any[];
            const site = resources?.find((r: any) => r.scopes?.includes('read:jira-work'));
            if (!site) return [];

            const jql = encodeURIComponent('assignee = currentUser() AND resolution = EMPTY ORDER BY updated DESC');
            const url = `https://api.atlassian.com/ex/jira/${site.id}/rest/api/3/search?jql=${jql}&maxResults=${limit}&fields=summary,status`;

            const resp = await fetch(url, {
                headers: {
                    Authorization: `Bearer ${token}`,
                    'Accept': 'application/json'
                }
            });

            if (!resp.ok) return [];

            const data = await resp.json() as any;
            const issues = data?.issues || [];

            return issues.map((i: any) => ({
                key: i.key,
                summary: i.fields?.summary || '',
                url: `https://${site.url}/browse/${i.key}`,
                status: i.fields?.status?.name
            }));
        } catch (error) {
            console.error('OAuth fetch error:', error);
            return [];
        }
    } private async fetchWithBasicAuth(token: string, limit: number): Promise<JiraIssue[]> {
        try {
            const cfg = vscode.workspace.getConfiguration('aep');
            const baseUrl = cfg.get<string>('jira.baseUrl');
            if (!baseUrl) return [];

            const jql = encodeURIComponent('assignee = currentUser() AND resolution = EMPTY ORDER BY updated DESC');
            const url = `${baseUrl}/rest/api/3/search?jql=${jql}&maxResults=${limit}&fields=summary,status`;

            const resp = await fetch(url, {
                headers: {
                    Authorization: `Basic ${token}`,
                    'Accept': 'application/json'
                }
            });

            if (!resp.ok) return [];

            const data = await resp.json() as any;
            const issues = data?.issues || [];

            return issues.map((i: any) => ({
                key: i.key,
                summary: i.fields?.summary || '',
                url: `${baseUrl}/browse/${i.key}`,
                status: i.fields?.status?.name
            }));
        } catch (error) {
            console.error('Basic auth fetch error:', error);
            return [];
        }
    }

    async mySprint(limit = 5): Promise<JiraIssue[]> {
        try {
            const token = await this.getToken();
            if (!token) return [];

            // Use OAuth method if available
            const raw = await this.context.secrets.get('aep.jira.oauth');
            if (raw) {
                return this.fetchSprintWithOAuth(token, limit);
            } else {
                return this.fetchSprintWithBasicAuth(token, limit);
            }
        } catch (error) {
            console.error('Failed to fetch sprint issues:', error);
            return [];
        }
    }

    private async fetchSprintWithOAuth(token: string, limit: number): Promise<JiraIssue[]> {
        try {
            // Get accessible resources first
            const resResp = await fetch('https://api.atlassian.com/oauth/token/accessible-resources', {
                headers: {
                    Authorization: `Bearer ${token}`,
                    'Accept': 'application/json'
                }
            });

            if (!resResp.ok) return [];

            const resources = await resResp.json() as any[];
            const site = resources?.find((r: any) => r.scopes?.includes('read:jira-work'));
            if (!site) return [];

            const jql = vscode.workspace.getConfiguration('aep').get<string>('jira.sprintJql') ||
                'sprint in openSprints() AND assignee = currentUser() ORDER BY updated DESC';
            const encodedJql = encodeURIComponent(jql);
            const url = `https://api.atlassian.com/ex/jira/${site.id}/rest/api/3/search?jql=${encodedJql}&maxResults=${limit}&fields=summary,status`;

            const resp = await fetch(url, {
                headers: {
                    Authorization: `Bearer ${token}`,
                    'Accept': 'application/json'
                }
            });

            if (!resp.ok) return [];

            const data = await resp.json() as any;
            const issues = data?.issues || [];

            return issues.map((i: any) => ({
                key: i.key,
                summary: i.fields?.summary || '',
                url: `https://${site.url}/browse/${i.key}`,
                status: i.fields?.status?.name
            }));
        } catch (error) {
            console.error('OAuth sprint fetch error:', error);
            return [];
        }
    }

    private async fetchSprintWithBasicAuth(token: string, limit: number): Promise<JiraIssue[]> {
        try {
            const cfg = vscode.workspace.getConfiguration('aep');
            const baseUrl = cfg.get<string>('jira.baseUrl')!;

            const jql = cfg.get<string>('jira.sprintJql') ||
                'sprint in openSprings() AND assignee = currentUser() ORDER BY updated DESC';
            const encodedJql = encodeURIComponent(jql);
            const url = `${baseUrl}/rest/api/3/search?jql=${encodedJql}&maxResults=${limit}&fields=summary,status`;

            const resp = await fetch(url, {
                headers: {
                    Authorization: `Basic ${token}`,
                    'Accept': 'application/json'
                }
            });

            if (!resp.ok) return [];

            const data = await resp.json() as any;
            const issues = data?.issues || [];

            return issues.map((i: any) => ({
                key: i.key,
                summary: i.fields?.summary || '',
                url: `${baseUrl}/browse/${i.key}`,
                status: i.fields?.status?.name
            }));
        } catch (error) {
            console.error('Basic auth sprint fetch error:', error);
            return [];
        }
    }
}

export class GithubClient {
    async connected(): Promise<boolean> {
        try {
            const session = await vscode.authentication.getSession('github', ['read:user', 'repo'], { createIfNone: false });
            return !!session?.accessToken;
        } catch {
            return false;
        }
    }

    private async getToken(): Promise<string | undefined> {
        try {
            const session = await vscode.authentication.getSession('github', ['read:user', 'repo'], { createIfNone: false });
            return session?.accessToken;
        } catch {
            return undefined;
        }
    }

    async myOpenPRs(limit = 5): Promise<GhPr[]> {
        const token = await this.getToken();
        if (!token) return [];

        try {
            // Get current user
            const userResp = await fetch('https://api.github.com/user', {
                headers: {
                    Authorization: `Bearer ${token}`,
                    'Accept': 'application/vnd.github+json'
                }
            });

            if (!userResp.ok) return [];

            const user = await userResp.json() as any;
            const login = user?.login;
            if (!login) return [];

            // Search for open PRs by this user
            const query = encodeURIComponent(`is:pr is:open author:${login}`);
            const url = `https://api.github.com/search/issues?q=${query}&per_page=${limit}`;

            const resp = await fetch(url, {
                headers: {
                    Authorization: `Bearer ${token}`,
                    'Accept': 'application/vnd.github+json'
                }
            });

            if (!resp.ok) return [];

            const data = await resp.json() as any;
            const items = data?.items || [];

            return items.map((i: any) => ({
                id: i.id,
                title: i.title,
                url: i.html_url,
                repo: (i.repository_url || '').split('/').slice(-2).join('/'),
                state: 'open'
            }));
        } catch (error) {
            console.error('Failed to fetch GitHub PRs:', error);
            return [];
        }
    }

    async prsNeedingMyReview(limit = 5): Promise<GhPr[]> {
        const token = await this.getToken();
        if (!token) return [];

        try {
            // Get current user login
            const userResp = await fetch('https://api.github.com/user', {
                headers: {
                    Authorization: `Bearer ${token}`,
                    'Accept': 'application/vnd.github+json'
                }
            });

            if (!userResp.ok) return [];

            const user = await userResp.json() as any;
            const login = user?.login;
            if (!login) return [];

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

            if (!resp.ok) return [];

            const data = await resp.json() as any;
            const items = data?.items || [];

            return items.map((i: any) => ({
                id: i.id,
                title: i.title,
                url: i.html_url,
                repo: (i.repository_url || '').split('/').slice(-2).join('/'),
                state: 'open'
            }));
        } catch (error) {
            console.error('Failed to fetch PRs needing review:', error);
            return [];
        }
    }
}