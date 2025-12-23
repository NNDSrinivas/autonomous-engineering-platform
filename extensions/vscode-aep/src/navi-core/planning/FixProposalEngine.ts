// extensions/vscode-aep/src/navi-core/planning/FixProposalEngine.ts
import type { ClassifiedDiagnostic } from '../perception/DiagnosticClassifier';
import { BestFixSelector } from '../fix/BestFixSelector';
import * as crypto from 'crypto';
import * as fs from 'fs';

export type ProposalConfidence = 'low' | 'medium' | 'high';
export type RiskLevel = 'low' | 'medium' | 'high';

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
    // Phase 2.1: Risk-based fix flow (not binary auto/manual)
    riskLevel: RiskLevel;
    requiresChoice?: boolean; // If true, show alternatives for user selection
    alternatives?: FixProposal[]; // Alternative fix options for ambiguous cases
    // Phase 2.1: Safety and application metadata
    originalFileHash?: string;
    rangeStart?: { line: number; character: number };
    rangeEnd?: { line: number; character: number };
    replacementText?: string;
    // Phase 2.1.1: Speculative (AI-suggested) fixes that require preview
    speculative?: boolean;
    previewRequired?: boolean;
}

function makeId(file: string, line: number, issue: string): string {
    const base = `${file}:${line}:${issue}`;
    return Buffer.from(base).toString('base64');
}

// Phase 2.1.2: Generate concrete JSX alternatives with replacementText
// Extract tag name from error message and generate multiple valid fix options
function generateJsxAlternatives(baseLine: number, issue: string, fileText: string): FixProposal[] {
    const baseId = `jsx-alt-${baseLine}`;
    const lines = fileText.split('\n');
    const lineIdx = Math.max(0, Math.min(baseLine - 1, lines.length - 1));
    const lineText = lines[lineIdx] ?? '';

    // Try to extract tag name from error message (e.g., "JSX element 'div' has no corresponding closing tag")
    const tagMatch = issue.match(/element ['"](\w+)['"]/i);
    const tagName = tagMatch ? tagMatch[1] : 'div';

    // Alternative 1: Add closing tag at end of line
    const closingTag = `</${tagName}>`;
    const alt1Text = lineText.trimEnd() + closingTag;

    // Alternative 2: Remove/comment out the opening tag (less destructive)
    const alt2Text = lineText.replace(new RegExp(`<${tagName}[^>]*>`, 'g'), `{/* <${tagName}> */}`);

    // Alternative 3: Wrap in React Fragment
    const alt3Text = lineText.trimEnd() + '\n</>'; // assumes opening <> exists or will be added

    return [
        {
            id: `${baseId}-add-closing`,
            filePath: '', // Will be filled by caller
            line: baseLine,
            severity: 'error' as const,
            impact: 'introduced' as const,
            issue: `Add closing </${tagName}> tag`,
            rootCause: 'JSX element is not properly closed.',
            suggestedChange: `Insert </${tagName}> at the end of line ${baseLine}.`,
            confidence: 'medium' as const,
            canAutoFixLater: false,
            riskLevel: 'medium' as const,
            replacementText: alt1Text,
            rangeStart: { line: lineIdx, character: 0 },
            rangeEnd: { line: lineIdx, character: lineText.length }
        },
        {
            id: `${baseId}-comment-opening`,
            filePath: '',
            line: baseLine,
            severity: 'error' as const,
            impact: 'introduced' as const,
            issue: `Comment out opening <${tagName}> tag`,
            rootCause: 'JSX element may have unmatched opening tag.',
            suggestedChange: `Convert <${tagName}> to a comment for manual review.`,
            confidence: 'low' as const,
            canAutoFixLater: false,
            riskLevel: 'high' as const,
            replacementText: alt2Text,
            rangeStart: { line: lineIdx, character: 0 },
            rangeEnd: { line: lineIdx, character: lineText.length }
        },
        {
            id: `${baseId}-fragment-close`,
            filePath: '',
            line: baseLine,
            severity: 'error' as const,
            impact: 'introduced' as const,
            issue: 'Close with React Fragment </>',
            rootCause: 'JSX structure may need Fragment wrapper.',
            suggestedChange: 'Add </> to close Fragment (assumes <> exists above).',
            confidence: 'low' as const,
            canAutoFixLater: false,
            riskLevel: 'high' as const,
            replacementText: alt3Text,
            rangeStart: { line: lineIdx, character: 0 },
            rangeEnd: { line: lineIdx, character: lineText.length }
        }
    ];
}

export class FixProposalEngine {
    static generate(classified: ClassifiedDiagnostic[]): FixProposal[] {
        const proposals: FixProposal[] = [];

        // Only generate proposals for introduced and preExisting diagnostics (skip 'unrelated')
        const relevantDiags = classified.filter(d => d.impact !== 'unrelated');

        // Helper: detect parser-level errors which need speculative fixes
        const isParserError = (msg: string): boolean => {
            const m = msg.toLowerCase();
            return (
                m.includes('expression expected') ||
                m.includes('declaration or statement expected') ||
                m.includes('unexpected token') ||
                m.includes("')' expected") ||
                m.includes("'}' expected") ||
                m.includes('jsx') ||
                m.includes('expected corresponding')
            );
        };

        // Helper: generate speculative alternatives for preview (non-destructive)
        const generateSpeculativeFixes = (d: ClassifiedDiagnostic, fileText: string): FixProposal[] => {
            const baseId = `speculative-${d.file}-${d.line}`;
            const lines = fileText.split('\n');
            const idx = Math.max(0, Math.min(d.line - 1, lines.length - 1));
            const lineText = lines[idx] ?? '';

            // Very conservative suggestions for preview-only flow
            const alt1Text = lineText.replace(/[)\]}]+$/g, ''); // remove dangling closers at end of line
            const alt2Text = lineText.trim().length > 0 ? lineText + ' /* TODO: complete expression */' : '/* TODO: insert expression */';

            const mkAlt = (suffix: string, text: string, sugg: string): FixProposal => ({
                id: `${baseId}-${suffix}`,
                filePath: d.file,
                line: d.line,
                severity: d.severity,
                impact: d.impact as 'introduced' | 'preExisting',
                issue: d.message,
                rootCause: 'Parser-level syntax error; multiple valid fixes exist.',
                suggestedChange: sugg,
                confidence: 'medium',
                canAutoFixLater: false,
                riskLevel: 'medium',
                replacementText: text,
                speculative: true,
                previewRequired: true,
            });

            return [
                mkAlt('remove-dangling', alt1Text, 'Remove dangling closing token near error location.'),
                mkAlt('complete-expression', alt2Text, 'Insert placeholder to complete expression, to be refined in editor.'),
            ];
        };

        for (const d of relevantDiags) {
            const issue = d.message || 'Diagnostic';
            const lower = issue.toLowerCase();

            let rootCause = 'Needs investigation';
            let suggestedChange = 'Review and apply appropriate fix.';
            let confidence: ProposalConfidence = 'low';
            let canAutoFixLater = false;
            let riskLevel: RiskLevel = 'medium'; // Default to medium risk

            // Heuristics based on common messages
            if (lower.includes("'}' expected") || lower.includes("'}'")) {
                rootCause = 'Missing closing brace or bracket in block.';
                suggestedChange = 'Add the missing closing brace at the indicated location.';
                confidence = 'high';
                canAutoFixLater = true;
                riskLevel = 'low'; // Clear structural fix
            } else if (lower.includes('expected corresponding jsx closing tag') || lower.includes('</div>') || lower.includes('jsx')) {
                rootCause = 'JSX tag mismatch or unclosed element.';
                suggestedChange = 'Add missing closing tag, remove extra tag, or adjust structure.';
                confidence = 'medium';
                canAutoFixLater = true;
                riskLevel = 'medium'; // Structural but context-dependent
            } else if (lower.includes('declaration or statement expected')) {
                rootCause = 'Syntax error: malformed statement or missing token.';
                suggestedChange = 'Correct the syntax; ensure statements are complete and properly terminated.';
                confidence = 'medium';
                riskLevel = 'medium'; // Needs context
            } else if (lower.includes('catch or finally expected')) {
                rootCause = 'Incomplete try/catch/finally block.';
                suggestedChange = 'Add a catch or finally block to complete the try statement.';
                confidence = 'high';
                riskLevel = 'low'; // Clear structural requirement
            } else if (lower.includes('type') && lower.includes('is not assignable to type')) {
                rootCause = 'Type mismatch between assigned value and declared type.';
                suggestedChange = 'Adjust the declared type or the assigned value to match expected types.';
                confidence = 'medium';
                riskLevel = 'medium'; // Type changes need validation
            } else if (lower.includes('duplicate object key')) {
                rootCause = 'Duplicate key in object literal or JSON document.';
                suggestedChange = 'Remove or rename the duplicate key to ensure uniqueness.';
                confidence = 'high';
                canAutoFixLater = true;
                riskLevel = 'high'; // Semantic choice - which key to keep?
            } else if (lower.includes('commonjs module') && lower.includes('converted to an es module')) {
                rootCause = 'Module format mismatch (CommonJS vs ES Module).';
                suggestedChange = 'Convert exports to ES module syntax (export default / named exports) or adjust bundler config.';
                confidence = 'medium';
                riskLevel = 'high'; // Module refactoring has wide impact
            } else if (lower.includes('unused variable')) {
                rootCause = 'Declared variable is never used.';
                suggestedChange = 'Remove the variable or use it where intended.';
                confidence = 'high';
                canAutoFixLater = true;
                riskLevel = 'low'; // Safe cleanup
            } else if (lower.includes("')' expected") || lower.includes('expected')) {
                rootCause = 'Missing token (parenthesis, bracket, or brace).';
                suggestedChange = 'Insert the missing token at the indicated position to complete the syntax.';
                confidence = 'medium';
                riskLevel = 'medium'; // Location may be ambiguous
            }

            // Phase 2.1: Compute file hash for safety validation
            let originalFileHash: string | undefined;
            let fileText: string | undefined;
            try {
                if (fs.existsSync(d.file)) {
                    fileText = fs.readFileSync(d.file, 'utf8');
                    originalFileHash = crypto.createHash('sha256').update(fileText).digest('hex');
                }
            } catch (err) {
                console.warn(`[FixProposalEngine] Failed to hash file ${d.file}:`, err);
            }

            // Phase 2.1.2: Generate alternatives for parser/JSX ambiguity
            let alternatives: FixProposal[] | undefined;
            console.log(`[FixProposalEngine] Processing issue: "${issue.substring(0, 60)}..."`);
            console.log(`[FixProposalEngine] fileText available: ${Boolean(fileText)}`);

            if (fileText) {
                const isExpected = issue.includes('expected');
                const isJSX = issue.includes('JSX');
                const isIdentifier = issue.includes('Identifier');
                console.log(`[FixProposalEngine] Condition check - expected: ${isExpected}, JSX: ${isJSX}, Identifier: ${isIdentifier}`);

                if (isExpected || isJSX || isIdentifier) {
                    console.log(`[FixProposalEngine] Triggering generateJsxAlternatives for line ${d.line}`);
                    const rawAlts = generateJsxAlternatives(d.line, issue, fileText);
                    console.log(`[FixProposalEngine] Generated ${rawAlts.length} raw alternatives`);
                    alternatives = rawAlts.map(alt => ({
                        ...alt,
                        filePath: d.file,
                        originalFileHash
                    }));
                    console.log(`[FixProposalEngine] After mapping: ${alternatives.length} alternatives with filePath`);
                } else if (isParserError(issue)) {
                    console.log(`[FixProposalEngine] Triggering generateSpeculativeFixes`);
                    alternatives = generateSpeculativeFixes(d, fileText);
                    console.log(`[FixProposalEngine] Generated ${alternatives.length} speculative alternatives`);
                }
            } else {
                console.warn(`[FixProposalEngine] fileText is null/undefined for ${d.file}`);
            }

            const requiresChoice = Boolean(alternatives && alternatives.length > 0);
            const proposal: FixProposal = {
                id: makeId(d.file, d.line, issue),
                filePath: d.file,
                line: d.line,
                severity: d.severity,
                source: d.source,
                impact: d.impact as 'introduced' | 'preExisting',
                issue,
                rootCause,
                suggestedChange,
                confidence,
                canAutoFixLater,
                riskLevel, // Phase 2.1: Risk-based gating (low/medium/high)
                originalFileHash,
                requiresChoice: requiresChoice ? true : undefined,
                alternatives,
                speculative: requiresChoice ? true : undefined,
                previewRequired: requiresChoice ? true : undefined,
                // Range and replacement will be computed in Phase 2.1 Step 1.5 (actual fix logic)
                rangeStart: { line: d.line - 1, character: 0 }, // VS Code uses 0-based lines
                rangeEnd: { line: d.line, character: 0 },
                // Note: replacementText is computed later in extension.applyFix() based on context
            };

            console.log('[FixProposalEngine] Alternatives attached:', proposal.alternatives?.length, 'requiresChoice:', proposal.requiresChoice);

            proposals.push(proposal);
        }

        // Phase 2.2 Step 1: Use BestFixSelector to return only the single best fix
        // This eliminates alternatives from the UI and enables Copilot-like behavior
        console.log(`[FixProposalEngine] Generated ${proposals.length} proposals, selecting best fix`);

        const bestProposal = BestFixSelector.select(proposals);
        if (bestProposal) {
            console.log(`[FixProposalEngine] Selected: ${bestProposal.suggestedChange}`);
            return [bestProposal]; // Always return array with single best proposal
        } else {
            console.log('[FixProposalEngine] No viable proposals found');
            return [];
        }
    }
}
