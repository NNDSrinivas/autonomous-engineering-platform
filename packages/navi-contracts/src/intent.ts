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
  if (v === "clarify") return IntentKind.CLARIFY;
  if (v === "general_chat" || v === "general_question") return IntentKind.GENERAL_CHAT;

  // heuristic mapping (Phase 4.2 grounding starter)
  // For overlapping keywords, return the intent for whichever keyword appears first
  const patterns = [
    { keywords: ["fix", "error", "problem", "bug"], intent: IntentKind.FIX_PROBLEMS },
    { keywords: ["analy", "explain project", "repo"], intent: IntentKind.ANALYZE_PROJECT },
    { keywords: ["deploy", "release", "ship"], intent: IntentKind.DEPLOY },
    { keywords: ["clarif", "explain", "what"], intent: IntentKind.CLARIFY }
  ];

  let earliestMatch: { position: number; intent: IntentKind; keywordLength: number } = {
    position: v.length,
    intent: IntentKind.GENERAL_CHAT,
    keywordLength: 0
  };
  
  for (const pattern of patterns) {
    for (const keyword of pattern.keywords) {
      const position = v.indexOf(keyword);
      if (
        position !== -1 &&
        (position < earliestMatch.position ||
          (position === earliestMatch.position && keyword.length > earliestMatch.keywordLength))
      ) {
        earliestMatch = { position, intent: pattern.intent, keywordLength: keyword.length };
      }
    }
  }
  
  if (earliestMatch.position < v.length) {
    return earliestMatch.intent;
  }

  // default
  return IntentKind.GENERAL_CHAT;
}
