// src/api/navi/client.ts
import type { NaviChatMessage, NaviChatResponse } from "../../types/naviChat";
import { mapChatResponseToNaviChatMessage } from "../../types/naviChat";

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
): Promise<NaviChatMessage> {
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

    const data = (await res.json()) as NaviChatResponse;

    // Convert backend response to NaviChatMessage
    return mapChatResponseToNaviChatMessage(data, "assistant");
}
