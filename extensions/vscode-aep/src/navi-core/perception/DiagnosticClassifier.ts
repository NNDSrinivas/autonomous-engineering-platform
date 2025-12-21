// extensions/vscode-aep/src/navi-core/perception/DiagnosticClassifier.ts
/**
 * Phase 1.3: Diagnostics Classification (introduced vs preExisting)
 * Heuristic: diagnostics in changed files are marked as introduced, others preExisting.
 */
import * as path from 'path';
import type { NaviDiagnostic } from './DiagnosticsPerception';

export type DiagnosticImpact = 'introduced' | 'preExisting' | 'unrelated';

export interface ClassifiedDiagnostic extends NaviDiagnostic {
    impact: DiagnosticImpact;
}

export class DiagnosticClassifier {
    static classify(
        diagnostics: NaviDiagnostic[],
        workspaceRoot: string,
        changedRelativePaths: string[]
    ): ClassifiedDiagnostic[] {
        const changedAbs = new Set(
            changedRelativePaths
                .filter(Boolean)
                .map((p) => path.join(workspaceRoot, p))
                .map((p) => path.normalize(p))
        );
        const changedRel = new Set(
            changedRelativePaths
                .filter(Boolean)
                .map((p) => path.normalize(p))
        );

        return diagnostics.map((d) => {
            const abs = path.normalize(d.file);
            // Try to derive a relative path under workspace for fallback matching
            const rel = abs.startsWith(path.normalize(workspaceRoot + path.sep))
                ? path.normalize(abs.slice(path.normalize(workspaceRoot + path.sep).length))
                : undefined;

            const introduced = changedAbs.has(abs) || (rel ? changedRel.has(rel) : false);
            return { ...d, impact: introduced ? 'introduced' : 'preExisting' };
        });
    }
}
