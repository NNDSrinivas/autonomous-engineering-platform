import { describe, it, expect } from 'vitest';
import { normalizeIntentKind, IntentKind } from '../src/intent';

describe('normalizeIntentKind', () => {
  describe('exact matches (already-normalized)', () => {
    it('should return FIX_PROBLEMS for exact match', () => {
      expect(normalizeIntentKind('fix_problems')).toBe(IntentKind.FIX_PROBLEMS);
      expect(normalizeIntentKind('FIX_PROBLEMS')).toBe(IntentKind.FIX_PROBLEMS);
      expect(normalizeIntentKind(' fix_problems ')).toBe(IntentKind.FIX_PROBLEMS);
    });

    it('should return ANALYZE_PROJECT for exact match', () => {
      expect(normalizeIntentKind('analyze_project')).toBe(IntentKind.ANALYZE_PROJECT);
      expect(normalizeIntentKind('ANALYZE_PROJECT')).toBe(IntentKind.ANALYZE_PROJECT);
    });

    it('should return DEPLOY for exact match', () => {
      expect(normalizeIntentKind('deploy')).toBe(IntentKind.DEPLOY);
      expect(normalizeIntentKind('DEPLOY')).toBe(IntentKind.DEPLOY);
    });

    it('should return CLARIFY for exact match', () => {
      expect(normalizeIntentKind('clarify')).toBe(IntentKind.CLARIFY);
      expect(normalizeIntentKind('CLARIFY')).toBe(IntentKind.CLARIFY);
    });

    it('should return GENERAL_CHAT for exact matches', () => {
      expect(normalizeIntentKind('general_chat')).toBe(IntentKind.GENERAL_CHAT);
      expect(normalizeIntentKind('general_question')).toBe(IntentKind.GENERAL_CHAT);
    });
  });

  describe('heuristic mapping', () => {
    it('should map problem-related keywords to FIX_PROBLEMS', () => {
      expect(normalizeIntentKind('fix this bug')).toBe(IntentKind.FIX_PROBLEMS);
      expect(normalizeIntentKind('there is an error')).toBe(IntentKind.FIX_PROBLEMS);
      expect(normalizeIntentKind('I have a problem')).toBe(IntentKind.FIX_PROBLEMS);
      expect(normalizeIntentKind('bug report')).toBe(IntentKind.FIX_PROBLEMS);
    });

    it('should map analysis-related keywords to ANALYZE_PROJECT', () => {
      expect(normalizeIntentKind('analyze this')).toBe(IntentKind.ANALYZE_PROJECT);
      expect(normalizeIntentKind('explain project structure')).toBe(IntentKind.ANALYZE_PROJECT);
      expect(normalizeIntentKind('tell me about this repo')).toBe(IntentKind.ANALYZE_PROJECT);
    });

    it('should map deployment-related keywords to DEPLOY', () => {
      expect(normalizeIntentKind('deploy to production')).toBe(IntentKind.DEPLOY);
      expect(normalizeIntentKind('release this version')).toBe(IntentKind.DEPLOY);
      expect(normalizeIntentKind('ship to staging')).toBe(IntentKind.DEPLOY);
    });

    it('should map clarification-related keywords to CLARIFY', () => {
      expect(normalizeIntentKind('clarify this')).toBe(IntentKind.CLARIFY);
      expect(normalizeIntentKind('what does this do')).toBe(IntentKind.CLARIFY);
      expect(normalizeIntentKind('explain how this works')).toBe(IntentKind.CLARIFY);
    });
  });

  describe('edge cases', () => {
    it('should handle null and undefined inputs', () => {
      expect(normalizeIntentKind(null)).toBe(IntentKind.GENERAL_CHAT);
      expect(normalizeIntentKind(undefined)).toBe(IntentKind.GENERAL_CHAT);
    });

    it('should handle empty strings', () => {
      expect(normalizeIntentKind('')).toBe(IntentKind.GENERAL_CHAT);
      expect(normalizeIntentKind('   ')).toBe(IntentKind.GENERAL_CHAT);
    });

    it('should default to GENERAL_CHAT for unknown inputs', () => {
      expect(normalizeIntentKind('random text')).toBe(IntentKind.GENERAL_CHAT);
      expect(normalizeIntentKind('hello world')).toBe(IntentKind.GENERAL_CHAT);
      expect(normalizeIntentKind('xyz123')).toBe(IntentKind.GENERAL_CHAT);
    });

    it('should handle case sensitivity', () => {
      expect(normalizeIntentKind('FIX THIS BUG')).toBe(IntentKind.FIX_PROBLEMS);
      expect(normalizeIntentKind('Deploy To Production')).toBe(IntentKind.DEPLOY);
      expect(normalizeIntentKind('ANALYZE PROJECT')).toBe(IntentKind.ANALYZE_PROJECT);
    });
  });

  describe('priority handling', () => {
    it('should prioritize exact matches over heuristics', () => {
      expect(normalizeIntentKind('fix_problems')).toBe(IntentKind.FIX_PROBLEMS);
      expect(normalizeIntentKind('analyze_project')).toBe(IntentKind.ANALYZE_PROJECT);
    });

    it('should handle overlapping keywords correctly', () => {
      // "fix" should match FIX_PROBLEMS heuristic first
      expect(normalizeIntentKind('fix and deploy')).toBe(IntentKind.FIX_PROBLEMS);
      // "deploy" should match DEPLOY heuristic first
      expect(normalizeIntentKind('deploy and analyze')).toBe(IntentKind.DEPLOY);
    });
  });
});