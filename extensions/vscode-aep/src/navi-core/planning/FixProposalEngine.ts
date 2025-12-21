// extensions/vscode-aep/src/navi-core/planning/FixProposalEngine.ts
import type { ClassifiedDiagnostic } from '../perception/DiagnosticClassifier';

export type ProposalConfidence = 'low' | 'medium' | 'high';

export interface FixProposal {
  id: string;
  filePath: string;
  line: number;
  severity: 'error' | 'warning' | 'info';
  source?: string;
  impact: 'introduced' | 'preExisting';
  issue: string;
  rootCause: string;
  suggestedChange: string;
  confidence: ProposalConfidence;
  canAutoFixLater: boolean;
}

function makeId(file: string, line: number, issue: string): string {
  const base = `${file}:${line}:${issue}`;
  return Buffer.from(base).toString('base64');
}

export class FixProposalEngine {
  static generate(classified: ClassifiedDiagnostic[]): FixProposal[] {
    const proposals: FixProposal[] = [];

    for (const d of classified) {
      const issue = d.message || 'Diagnostic';
      const lower = issue.toLowerCase();

      let rootCause = 'Needs investigation';
      let suggestedChange = 'Review and apply appropriate fix.';
      let confidence: ProposalConfidence = 'low';
      let canAutoFixLater = false;

      // Heuristics based on common messages
      if (lower.includes("'}' expected") || lower.includes("'}'")) {
        rootCause = 'Missing closing brace or bracket in block.';
        suggestedChange = 'Add the missing closing brace at the indicated location.';
        confidence = 'high';
        canAutoFixLater = true;
      } else if (lower.includes('declaration or statement expected')) {
        rootCause = 'Syntax error: malformed statement or missing token.';
        suggestedChange = 'Correct the syntax; ensure statements are complete and properly terminated.';
        confidence = 'medium';
      } else if (lower.includes('catch or finally expected')) {
        rootCause = 'Incomplete try/catch/finally block.';
        suggestedChange = 'Add a catch or finally block to complete the try statement.';
        confidence = 'high';
      } else if (lower.includes('type') && lower.includes('is not assignable to type')) {
        rootCause = 'Type mismatch between assigned value and declared type.';
        suggestedChange = 'Adjust the declared type or the assigned value to match expected types.';
        confidence = 'medium';
      } else if (lower.includes('duplicate object key')) {
        rootCause = 'Duplicate key in object literal or JSON document.';
        suggestedChange = 'Remove or rename the duplicate key to ensure uniqueness.';
        confidence = 'high';
        canAutoFixLater = true;
      } else if (lower.includes('commonjs module') && lower.includes('converted to an es module')) {
        rootCause = 'Module format mismatch (CommonJS vs ES Module).';
        suggestedChange = 'Convert exports to ES module syntax (export default / named exports) or adjust bundler config.';
        confidence = 'medium';
      } else if (lower.includes('unused variable')) {
        rootCause = 'Declared variable is never used.';
        suggestedChange = 'Remove the variable or use it where intended.';
        confidence = 'high';
        canAutoFixLater = true;
      } else if (lower.includes("')' expected") || lower.includes('expected')) {
        rootCause = 'Missing token (parenthesis, bracket, or brace).';
        suggestedChange = 'Insert the missing token at the indicated position to complete the syntax.';
        confidence = 'medium';
      }

      proposals.push({
        id: makeId(d.file, d.line, issue),
        filePath: d.file,
        line: d.line,
        severity: d.severity,
        source: d.source,
        impact: d.impact,
        issue,
        rootCause,
        suggestedChange,
        confidence,
        canAutoFixLater,
      });
    }

    return proposals;
  }
}
