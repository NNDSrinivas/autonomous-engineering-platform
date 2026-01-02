/**
 * Finding Deduplication
 * 
 * Removes duplicate security findings that represent the same underlying vulnerability.
 * Uses multiple strategies to identify and merge duplicates intelligently.
 */

import { Evidence, FindingSource, SecurityFinding } from '../types';

/**
 * Deduplication strategy weights for scoring matches
 */
const MATCH_WEIGHTS = {
    CVE_EXACT: 1.0,     // Same CVE ID = definite duplicate
    CVE_PARTIAL: 0.8,   // Overlapping CVE IDs
    COMPONENT_EXACT: 0.7, // Same component
    LOCATION_EXACT: 0.9,  // Same file and line
    LOCATION_NEAR: 0.6,   // Same file, nearby lines
    TYPE_MATCH: 0.3,      // Same vulnerability type
    TITLE_SIMILAR: 0.5,   // Similar titles
    DESCRIPTION_SIMILAR: 0.4 // Similar descriptions
};

/**
 * Threshold for considering findings as duplicates
 */
const DUPLICATE_THRESHOLD = 0.7;

/**
 * Deduplicate security findings using intelligent matching
 */
export function deduplicateFindings(findings: SecurityFinding[]): SecurityFinding[] {
    console.log(`🔄 Deduplicating ${findings.length} findings...`);

    if (findings.length <= 1) {
        return findings;
    }

    const duplicateGroups = findDuplicateGroups(findings);
    const deduplicated = mergeDuplicateGroups(duplicateGroups);

    const duplicatesRemoved = findings.length - deduplicated.length;
    if (duplicatesRemoved > 0) {
        console.log(`✅ Removed ${duplicatesRemoved} duplicate findings, ${deduplicated.length} unique findings remain`);
    } else {
        console.log(`✅ No duplicates found, all ${deduplicated.length} findings are unique`);
    }

    return deduplicated;
}

/**
 * Find groups of duplicate findings
 */
function findDuplicateGroups(findings: SecurityFinding[]): SecurityFinding[][] {
    const processed = new Set<string>();
    const duplicateGroups: SecurityFinding[][] = [];

    for (let i = 0; i < findings.length; i++) {
        const finding = findings[i];

        if (processed.has(finding.id)) {
            continue; // Already processed as part of another group
        }

        const group = [finding];
        processed.add(finding.id);

        // Find all duplicates of this finding
        for (let j = i + 1; j < findings.length; j++) {
            const candidate = findings[j];

            if (processed.has(candidate.id)) {
                continue;
            }

            const similarity = calculateSimilarity(finding, candidate);
            if (similarity >= DUPLICATE_THRESHOLD) {
                group.push(candidate);
                processed.add(candidate.id);
            }
        }

        duplicateGroups.push(group);
    }

    return duplicateGroups;
}

/**
 * Calculate similarity score between two findings
 */
function calculateSimilarity(finding1: SecurityFinding, finding2: SecurityFinding): number {
    let totalScore = 0;
    let maxPossibleScore = 0;

    // CVE matching (highest weight)
    const cveScore = calculateCVEMatch(finding1.cveIds, finding2.cveIds);
    if (cveScore > 0) {
        totalScore += cveScore * MATCH_WEIGHTS.CVE_EXACT;
        maxPossibleScore += MATCH_WEIGHTS.CVE_EXACT;
    }

    // Component matching
    const componentScore = calculateComponentMatch(finding1.component, finding2.component);
    totalScore += componentScore * MATCH_WEIGHTS.COMPONENT_EXACT;
    maxPossibleScore += MATCH_WEIGHTS.COMPONENT_EXACT;

    // Location matching
    const locationScore = calculateLocationMatch(finding1, finding2);
    totalScore += locationScore.score * locationScore.weight;
    maxPossibleScore += locationScore.weight;

    // Type matching
    const typeScore = finding1.type === finding2.type ? 1.0 : 0.0;
    totalScore += typeScore * MATCH_WEIGHTS.TYPE_MATCH;
    maxPossibleScore += MATCH_WEIGHTS.TYPE_MATCH;

    // Title similarity
    const titleScore = calculateTextSimilarity(finding1.title, finding2.title);
    totalScore += titleScore * MATCH_WEIGHTS.TITLE_SIMILAR;
    maxPossibleScore += MATCH_WEIGHTS.TITLE_SIMILAR;

    // Description similarity (only if titles are somewhat similar)
    if (titleScore > 0.3) {
        const descScore = calculateTextSimilarity(finding1.description, finding2.description);
        totalScore += descScore * MATCH_WEIGHTS.DESCRIPTION_SIMILAR;
        maxPossibleScore += MATCH_WEIGHTS.DESCRIPTION_SIMILAR;
    }

    return maxPossibleScore > 0 ? totalScore / maxPossibleScore : 0;
}

/**
 * Calculate CVE match score
 */
function calculateCVEMatch(cves1?: string[], cves2?: string[]): number {
    if (!cves1 || !cves2 || cves1.length === 0 || cves2.length === 0) {
        return 0;
    }

    const set1 = new Set(cves1);
    const set2 = new Set(cves2);

    // Find intersection
    const intersection = [...set1].filter(cve => set2.has(cve));

    if (intersection.length === 0) {
        return 0;
    }

    // Exact match if all CVEs are the same
    if (intersection.length === set1.size && intersection.length === set2.size) {
        return 1.0;
    }

    // Partial match based on overlap
    const union = new Set([...set1, ...set2]);
    return intersection.length / union.size;
}

/**
 * Calculate component match score
 */
function calculateComponentMatch(component1: string, component2: string): number {
    if (component1 === component2) {
        return 1.0;
    }

    // Normalize component names for comparison
    const norm1 = normalizeComponentName(component1);
    const norm2 = normalizeComponentName(component2);

    if (norm1 === norm2) {
        return 0.9;
    }

    // Check if one is contained in the other (e.g., "lodash" vs "lodash@4.17.20")
    if (norm1.includes(norm2) || norm2.includes(norm1)) {
        return 0.8;
    }

    return 0;
}

/**
 * Normalize component name for comparison
 */
function normalizeComponentName(component: string): string {
    return component
        .toLowerCase()
        .replace(/@.*$/, '') // Remove version
        .replace(/[^a-z0-9\-_]/g, '') // Remove special chars
        .trim();
}

/**
 * Calculate location match score
 */
function calculateLocationMatch(finding1: SecurityFinding, finding2: SecurityFinding): { score: number; weight: number } {
    const file1 = finding1.filePath;
    const file2 = finding2.filePath;
    const line1 = finding1.lineNumber;
    const line2 = finding2.lineNumber;

    // If both have file paths
    if (file1 && file2) {
        if (file1 === file2) {
            // Same file - check line numbers
            if (line1 && line2) {
                const lineDiff = Math.abs(line1 - line2);
                if (lineDiff === 0) {
                    // Exact same location
                    return { score: 1.0, weight: MATCH_WEIGHTS.LOCATION_EXACT };
                } else if (lineDiff <= 5) {
                    // Nearby lines (within 5 lines)
                    const score = Math.max(0, 1.0 - (lineDiff / 10));
                    return { score, weight: MATCH_WEIGHTS.LOCATION_NEAR };
                }
            } else {
                // Same file, no line info
                return { score: 0.7, weight: MATCH_WEIGHTS.LOCATION_NEAR };
            }
        } else {
            // Different files
            return { score: 0, weight: MATCH_WEIGHTS.LOCATION_EXACT };
        }
    }

    // No meaningful location comparison possible
    return { score: 0, weight: 0 };
}

/**
 * Calculate text similarity using simple algorithm
 */
function calculateTextSimilarity(text1: string, text2: string): number {
    if (text1 === text2) {
        return 1.0;
    }

    const norm1 = normalizeText(text1);
    const norm2 = normalizeText(text2);

    if (norm1 === norm2) {
        return 0.95;
    }

    // Calculate word overlap
    const words1 = new Set(norm1.split(' ').filter(w => w.length > 2));
    const words2 = new Set(norm2.split(' ').filter(w => w.length > 2));

    if (words1.size === 0 || words2.size === 0) {
        return 0;
    }

    const intersection = [...words1].filter(word => words2.has(word));
    const union = new Set([...words1, ...words2]);

    return intersection.length / union.size;
}

/**
 * Normalize text for comparison
 */
function normalizeText(text: string): string {
    return text
        .toLowerCase()
        .replace(/[^a-z0-9\s]/g, ' ')  // Replace special chars with spaces
        .replace(/\s+/g, ' ')          // Normalize whitespace
        .trim();
}

/**
 * Merge duplicate groups into single findings
 */
function mergeDuplicateGroups(groups: SecurityFinding[][]): SecurityFinding[] {
    return groups.map(group => {
        if (group.length === 1) {
            return group[0]; // No duplicates
        }

        return mergeDuplicateFindings(group);
    });
}

/**
 * Merge multiple duplicate findings into a single representative finding
 */
function mergeDuplicateFindings(duplicates: SecurityFinding[]): SecurityFinding {
    console.log(`🔗 Merging ${duplicates.length} duplicate findings: ${duplicates.map(d => d.id).join(', ')}`);

    // Choose the "best" finding as base
    const baseFinding = chooseBestFinding(duplicates);

    // Merge data from all findings
    const merged: SecurityFinding = {
        ...baseFinding,

        // Merge IDs to track original findings
        id: `merged-${duplicates.map(d => d.id).sort().join('-')}`,

        // Combine CVE IDs
        cveIds: mergeCVEIds(duplicates.map(d => d.cveIds ?? [])),

        // Use most specific component name
        component: chooseBestComponent(duplicates.map(d => d.component)),

        // Use most complete description
        description: chooseBestDescription(duplicates.map(d => d.description)),

        // Merge evidence from all findings
        evidence: mergeEvidence(duplicates.flatMap(d => d.evidence ?? [])),

        // Track all contributing sources
        source: mergeSources(duplicates.map(d => d.source)),

        // Use highest confidence
        confidence: Math.max(...duplicates.map(d => d.confidence)),

        // Use earliest detection time
        detectedAt: earliestTimestamp(duplicates.map(d => d.detectedAt).filter(Boolean) as string[])
    };

    return merged;
}

/**
 * Choose the best finding as base for merging
 */
function chooseBestFinding(findings: SecurityFinding[]): SecurityFinding {
    // Preference order: highest confidence, then most complete data, then CI sources
    return findings.sort((a, b) => {
        // Higher confidence first
        if (a.confidence !== b.confidence) {
            return b.confidence - a.confidence;
        }

        // More complete findings first (more evidence)
        const aEvidence = a.evidence ?? [];
        const bEvidence = b.evidence ?? [];
        if (aEvidence.length !== bEvidence.length) {
            return bEvidence.length - aEvidence.length;
        }

        // Prefer CI sources (usually more authoritative)
        const sourcePreference = {
            [FindingSource.CI_SECURITY]: 4,
            CI_REPORT: 4,
            [FindingSource.DEPENDENCY_SCANNER]: 3,
            DEPENDENCY_SCAN: 3,
            [FindingSource.SAST_SCANNER]: 2,
            SAST: 2,
            [FindingSource.CONFIG_SCANNER]: 2,
            CONFIG_SCAN: 2,
            [FindingSource.SECRET_SCANNER]: 1,
            [FindingSource.TEST]: 0
        };

        const aScore = scoreSource(a.source, sourcePreference);
        const bScore = scoreSource(b.source, sourcePreference);

        return bScore - aScore;
    })[0];
}

/**
 * Merge CVE IDs from multiple findings
 */
function mergeCVEIds(cveArrays: string[][]): string[] {
    if (cveArrays.length === 0) {
        return [];
    }

    const allCVEs = new Set<string>();
    for (const cves of cveArrays) {
        for (const cve of cves) {
            allCVEs.add(cve);
        }
    }

    return allCVEs.size > 0 ? Array.from(allCVEs).sort() : [];
}

/**
 * Choose best component name from multiple options
 */
function chooseBestComponent(components: string[]): string {
    // Prefer more specific component names (longer, with version info)
    return components.sort((a, b) => {
        // Prefer components with version info
        const aHasVersion = /@\d+/.test(a);
        const bHasVersion = /@\d+/.test(b);

        if (aHasVersion && !bHasVersion) return -1;
        if (!aHasVersion && bHasVersion) return 1;

        // Prefer longer names (more specific)
        return b.length - a.length;
    })[0];
}

/**
 * Choose best description from multiple options
 */
function chooseBestDescription(descriptions: string[]): string {
    // Prefer longer, more detailed descriptions
    return descriptions.sort((a, b) => b.length - a.length)[0];
}

/**
 * Merge evidence arrays and remove duplicates
 */
function mergeEvidence(evidenceArray: Evidence[]): Evidence[] {
    const uniqueEvidence = new Map<string, Evidence>();

    for (const evidence of evidenceArray) {
        // Create key for deduplication
        const key = `${evidence.type}-${evidence.filePath || 'no-file'}-${evidence.content.substring(0, 100)}`;

        if (!uniqueEvidence.has(key)) {
            uniqueEvidence.set(key, evidence);
        }
    }

    return Array.from(uniqueEvidence.values());
}

/**
 * Find earliest timestamp from array
 */
function earliestTimestamp(timestamps: string[]): string {
    if (timestamps.length === 0) {
        return new Date().toISOString();
    }
    return timestamps.sort((a, b) => new Date(a).getTime() - new Date(b).getTime())[0];
}

function mergeSources(sources: Array<SecurityFinding['source']>): string {
    const merged = new Set<string>();

    for (const source of sources) {
        const value = String(source);
        value.split(',').forEach(entry => {
            const trimmed = entry.trim();
            if (trimmed) {
                merged.add(trimmed);
            }
        });
    }

    return Array.from(merged.values()).join(',');
}

function scoreSource(
    source: SecurityFinding['source'],
    preference: Record<string, number>
): number {
    const values = String(source).split(',').map(entry => entry.trim()).filter(Boolean);
    return values.reduce((max, value) => Math.max(max, preference[value] || 0), 0);
}

/**
 * Get deduplication statistics
 */
export function getDeduplicationStats(before: SecurityFinding[], after: SecurityFinding[]): {
    originalCount: number;
    deduplicatedCount: number;
    duplicatesRemoved: number;
    duplicateRate: number;
    groupSizes: number[];
} {
    const duplicateGroups = findDuplicateGroups(before);
    const groupSizes = duplicateGroups.map(group => group.length);

    return {
        originalCount: before.length,
        deduplicatedCount: after.length,
        duplicatesRemoved: before.length - after.length,
        duplicateRate: (before.length - after.length) / before.length,
        groupSizes
    };
}
