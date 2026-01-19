export type ActivityEvent =
  | { id: string; ts: number; runId: string; type: "phase_start"; title: string; parentId?: string }
  | { id: string; ts: number; runId: string; type: "phase_end"; phaseId: string }
  | { id: string; ts: number; runId: string; type: "tool_search"; query: string; cwd?: string; files?: string[] }
  | { id: string; ts: number; runId: string; type: "file_read"; path: string; range?: { startLine: number; endLine: number } }
  | { id: string; ts: number; runId: string; type: "analysis"; text: string }
  | { id: string; ts: number; runId: string; type: "edit"; path: string; summary?: string; diffUnified?: string; stats?: { added: number; removed: number } }
  | { id: string; ts: number; runId: string; type: "progress"; label: string; percent?: number }
  | { id: string; ts: number; runId: string; type: "error"; message: string; details?: string };
