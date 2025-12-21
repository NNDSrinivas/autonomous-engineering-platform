// extensions/vscode-aep/src/navi-core/assessment/NaviAssessment.ts
import type { ClassifiedDiagnostic } from '../perception/DiagnosticClassifier';
import type { FixProposal } from '../planning/FixProposalEngine';

export interface NaviAssessmentCounts {
  totalIssues: number;
  introducedIssues: number;
  preExistingIssues: number;
  fixableIssues: number;
  warnings: number;
}

export function computeAssessmentCounts(
  diagnostics: ClassifiedDiagnostic[],
  proposals: FixProposal[] = []
): NaviAssessmentCounts {
  const totalIssues = diagnostics.length;
  const introducedIssues = diagnostics.filter(d => d.impact === 'introduced').length;
  const preExistingIssues = diagnostics.filter(d => d.impact === 'preExisting').length;
  const warnings = diagnostics.filter(d => d.severity === 'warning').length;
  const fixableIssues = proposals.length;

  return {
    totalIssues,
    introducedIssues,
    preExistingIssues,
    fixableIssues,
    warnings,
  };
}
