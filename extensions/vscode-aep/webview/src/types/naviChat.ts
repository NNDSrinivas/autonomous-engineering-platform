// NAVI Chat Types

export interface NaviChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp?: number;
  actions?: NaviAction[];
  patches?: NaviFilePatch[];
}

export interface NaviAction {
  id: string;
  title: string;
  description?: string;
  patches?: NaviFilePatch[];
  approvalRequired?: boolean;
}

export interface NaviFilePatch {
  path: string;
  kind: "create" | "edit" | "delete";
  newText?: string;
  description?: string;
}

export interface NaviChatResponse {
  content: string;
  actions?: NaviAction[];
}

// Helper to map API response to chat message
export function mapChatResponseToNaviChatMessage(
  response: NaviChatResponse,
  role: "user" | "assistant" = "assistant"
): NaviChatMessage {
  return {
    id: Date.now().toString(),
    role,
    content: response.content,
    timestamp: Date.now(),
    actions: response.actions || [],
  };
}
