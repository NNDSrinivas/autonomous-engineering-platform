// src/api/navi/client.ts
import {
    ChatResponse,
    NaviIntent,
    extractNaviIntent,
    mapChatResponseToNaviChatMessage,
} from "./types";
import {
    NaviChatMessage,
    NaviChatMessageIntent,
    NaviChatMessageText,
} from "../../types/naviChat";

/**
 * Low-level API call to NAVI backend.
 *
 * Assumes: POST /api/navi/chat
 * Body shape is up to you; here we send basic "content" (user text).
 * Adjust URL and payload if your backend expects something different.
 */
export async function sendNaviChat(
    userText: string,
    extraPayload?: Record<string, any>,
): Promise<ChatResponse> {
    // Use the backend base URL from window (set by extension or fallback)
    const backendBase = (window as any).__AEP_BACKEND_BASE_URL__ || "http://127.0.0.1:8787";
    const url = `${backendBase}/api/navi/chat`;

    // Get workspace context from window (set by extension)
    const workspace = (window as any).__WORKSPACE_CONTEXT__;
    const workspaceRoot = (window as any).__WORKSPACE_ROOT__ || null;

    const body = {
        message: userText,
        workspace,
        workspace_root: workspaceRoot,
        ...(extraPayload ?? {}),
    };

    console.log("[NAVI Client] Sending request:", {
        url,
        backendBase,
        workspaceRoot,
        windowKeys: Object.keys(window).filter(k => k.includes('AEP') || k.includes('WORKSPACE')),
        messageLength: userText.length,
        bodyKeys: Object.keys(body),
        fullBody: body,
    });

    console.log("[NAVI Client] Full request body JSON:", JSON.stringify(body, null, 2));

    const res = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
    });

    if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(
            `Failed to send NAVI chat: ${res.status} ${res.statusText} ${text}`,
        );
    }

    const data = (await res.json()) as ChatResponse;
    return data;
}

/**
 * Map a single ChatResponse into one UI-facing NaviChatMessage.
 *
 * - If an intent is detected (CHECK_ERRORS_AND_FIX), returns kind: "navi-intent".
 * - Otherwise, returns kind: "text".
 */
export function mapChatResponseToNaviChatMessage(options: {
    response: ChatResponse;
    lastUserMessage: string;
    role?: "assistant";
    repoPath?: string;
    branch?: string;
}): NaviChatMessage {
    const { response, lastUserMessage, role = "assistant", repoPath, branch } = options;

    const now = new Date().toISOString();
    const id = `assistant-${Date.now()}-${Math.random().toString(36).slice(2)}`;

    const baseMeta = {
        actions: response.actions ?? [],
        sources: response.sources ?? [],
        agentRun: response.agentRun ?? null,
        controls: response.controls ?? null,
        changes: response.changes ?? null,
        state: response.state ?? null,
        durationMs: response.duration_ms ?? null,
    };

    const textContent = response.reply || response.content || "";

    // Try to detect a frontend intent from backend response
    const intent: NaviIntent = extractNaviIntent(lastUserMessage, response);

    if (intent === "CHECK_ERRORS_AND_FIX") {
        const intentMsg: NaviChatMessageIntent = {
            id,
            createdAt: now,
            role,
            kind: "navi-intent",
            intent,
            text: textContent,
            repoPath,
            branch,
            meta: baseMeta,
        };
        return intentMsg;
    }

    const textMsg: NaviChatMessageText = {
        id,
        createdAt: now,
        role,
        kind: "text",
        text: textContent,
        meta: {
            actions: baseMeta.actions || [],
            sources: baseMeta.sources || [],
            agentRun: baseMeta.agentRun || null,
            controls: baseMeta.controls || null,
            changes: baseMeta.changes || null,
            state: baseMeta.state || null,
            durationMs: baseMeta.durationMs || null,
        },
    };
    return textMsg;
}
