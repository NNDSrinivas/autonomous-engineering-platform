// DEPRECATED: This file has been replaced by Phase 4.1.2 planning architecture
// Intent → Plan → Tool → Verify flow is now handled by:
// - webview/src/services/intentService.ts (frontend)
// - backend/api/navi.py (backend planning endpoints)
// - backend/agent/intent_classifier.py (canonical classifier)

export interface Intent {
  type: string;
  confidence: number;
  raw: string;
}

export class IntentClassifier {
  static classify(message: string): Intent {
    // Stub for compilation compatibility
    return {
      type: 'UNKNOWN',
      confidence: 0.5,
      raw: message
    };
  }
}