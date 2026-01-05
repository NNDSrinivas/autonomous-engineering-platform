export type DiagnosticItem = {
  uri: string;
  message: string;
  severity: "error" | "warning" | "info" | "hint";
  source?: string;
  code?: string | number;
  startLine?: number;
  startCharacter?: number;
  endLine?: number;
  endCharacter?: number;
};

export type ContextPack = {
  workspaceName?: string;
  workspaceRoot?: string;
  branch?: string;
  activeFile?: string;
  diagnostics?: {
    count: number;
    items: DiagnosticItem[];
  };
};