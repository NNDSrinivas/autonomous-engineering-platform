// src/api/navi/client.ts
import type { NaviChatMessage, NaviChatResponse } from "../../types/naviChat";
import { mapChatResponseToNaviChatMessage } from "../../types/naviChat";
import { ORG, USER_ID } from "../client";
import { getAuthToken } from "../../utils/auth";

/**
 * Resolve the backend base URL.
 * Priority:
 * 1) Explicit override injected by the VS Code extension/webview
 * 2) Same-origin (works for local dev + prod)
 * 3) Legacy localhost fallback for standalone runs
 */
export function resolveBackendBase(): string {
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    const override = typeof window !== "undefined"
        ? (window as any).__AEP_BACKEND_BASE_URL__
        : undefined;

    // Prefer VS Code-injected base, then origin, then dev default
    const base = override || origin || "http://127.0.0.1:8787";
    const cleaned = base.replace(/\/$/, "");
    // Ensure we never end up with /api/navi/chat appended
    return cleaned.replace(/\/api\/navi\/chat$/i, "");
}

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
    const backendBase = resolveBackendBase();
    const url = `${backendBase}/api/navi/chat`;

    // Get workspace context from window (set by extension)
    const workspace = (window as any).__WORKSPACE_CONTEXT__;
    const workspaceRoot = (window as any).__WORKSPACE_ROOT__ || null;

    // Build request body matching backend ChatRequest schema
    const body = {
        message: userText,
        model: extraPayload?.model || "gpt-4o-mini",
        mode: extraPayload?.mode || "chat-only",
        attachments: extraPayload?.attachments || [],
        workspace: workspace || null,
        workspace_root: workspaceRoot,
        user_id: extraPayload?.user_id || USER_ID,
    };

    console.log("[NAVI Client] Sending request:", {
        url,
        backendBase,
        workspaceRoot,
        windowKeys: Object.keys(window).filter(k => k.includes('AEP') || k.includes('WORKSPACE')),
        messageLength: userText.length,
        model: body.model,
        mode: body.mode,
    });

    console.log("[NAVI Client] Full request body JSON:", JSON.stringify(body, null, 2));

    try {
        const authToken = getAuthToken();
        const res = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Org-Id": ORG,
                ...(authToken
                    ? {
                        Authorization: authToken.startsWith("Bearer ")
                            ? authToken
                            : `Bearer ${authToken}`,
                    }
                    : {}),
            },
            body: JSON.stringify(body),
        });

        console.log("[NAVI Client] Response status:", res.status, res.statusText);

        const text = await res.text();
        console.log("[NAVI Client] Raw response:", text.substring(0, 500));

        if (!res.ok) {
            throw new Error(
                `Failed to send NAVI chat: ${res.status} ${res.statusText}\nBody: ${text}`,
            );
        }

        const data = JSON.parse(text) as NaviChatResponse;
        console.log("[NAVI Client] Parsed response:", data);

        // Convert backend response to NaviChatMessage
        return mapChatResponseToNaviChatMessage(data, "assistant");
    } catch (err: any) {
        console.error("[NAVI Client] Request failed:", err);
        // Graceful fallback so UI still shows a message
        return {
            id: `local-error-${Date.now()}`,
            role: "assistant",
            content:
                "I couldn't reach the NAVI backend. Please verify the backend is running and reachable. " +
                (err?.message ? `Details: ${err.message}` : ""),
        };
    }
}
