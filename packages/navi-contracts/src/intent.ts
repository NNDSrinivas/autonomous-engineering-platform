export const IntentKind = {
  GENERAL_CHAT: "GENERAL_CHAT",
  FIX_PROBLEMS: "FIX_PROBLEMS",
  ANALYZE_PROJECT: "ANALYZE_PROJECT",
  DEPLOY: "DEPLOY",
  CLARIFY: "CLARIFY"
} as const;

export type IntentKind = (typeof IntentKind)[keyof typeof IntentKind];

export type IntentClassification = {
  kind: IntentKind;
  confidence: number; // 0..1
  reason?: string;
  rawUserText: string;
};

export function normalizeIntentKind(input: string | undefined | null): IntentKind {
  const v = (input ?? "").trim().toLowerCase();

  // already-normalized
  if (v === "fix_problems") return IntentKind.FIX_PROBLEMS;
  if (v === "analyze_project") return IntentKind.ANALYZE_PROJECT;
  if (v === "deploy") return IntentKind.DEPLOY;
  if (v === "general_chat" || v === "general_question") return IntentKind.GENERAL_CHAT;

  // heuristic mapping (Phase 4.2 grounding starter)
  if (v.includes("fix") || v.includes("error") || v.includes("problem") || v.includes("bug")) return IntentKind.FIX_PROBLEMS;
  if (v.includes("analy") || v.includes("explain project") || v.includes("repo")) return IntentKind.ANALYZE_PROJECT;
  if (v.includes("deploy") || v.includes("release") || v.includes("ship")) return IntentKind.DEPLOY;

  // default
  return IntentKind.GENERAL_CHAT;
}