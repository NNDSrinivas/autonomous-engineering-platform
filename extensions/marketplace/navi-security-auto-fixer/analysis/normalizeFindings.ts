/**
 * Finding Normalization
 * 
 * Normalizes security findings from different sources into a consistent format.
 * Handles data validation, field mapping, and standardization.
 */

import { Evidence, FindingSource, SecurityFinding, SeverityLevel, VulnerabilityType } from '../types';

/**
 * Normalize findings from multiple sources into consistent format
 */
export function normalizeFindings(rawFindings: SecurityFinding[]): SecurityFinding[] {
    console.log(`📊 Normalizing ${rawFindings.length} raw findings...`);

    const normalizedFindings: SecurityFinding[] = [];

    for (const finding of rawFindings) {
        try {
            const normalized = normalizeFinding(finding);
            if (normalized && isValidFinding(normalized)) {
                normalizedFindings.push(normalized);
            } else {
                console.warn(`⚠️  Skipping invalid finding: ${finding.id}`);
            }
        } catch (error) {
            console.warn(`⚠️  Failed to normalize finding ${finding.id}:`, error);
        }
    }

    console.log(`✅ Normalized ${normalizedFindings.length} valid findings`);
    return normalizedFindings;
}

/**
 * Normalize individual finding
 */
function normalizeFinding(finding: SecurityFinding): SecurityFinding | null {
    // Ensure required fields exist
    if (!finding.id || !finding.type || !finding.severity) {
        console.warn('⚠️  Finding missing required fields:', finding);
        return null;
    }

    const result: SecurityFinding = {
        // Core identification
        id: normalizeId(finding.id),
        type: normalizeType(finding.type),
        severity: normalizeSeverity(finding.severity),

        // CVE information
        cveIds: normalizeCVEIds(finding.cveIds),

        // Location information
        component: normalizeComponent(finding.component),
        title: normalizeTitle(finding.title),
        description: normalizeDescription(finding.description),

        // Evidence
        evidence: normalizeEvidence(finding.evidence || []),

        // Metadata
        source: normalizeSource(finding.source),
        confidence: normalizeConfidence(finding.confidence),
        detectedAt: normalizeTimestamp(finding.detectedAt)
    };

    // Set optional properties conditionally
    const normalizedFilePath = normalizeFilePath(finding.filePath);
    if (normalizedFilePath !== undefined) {
        result.filePath = normalizedFilePath;
    }

    const normalizedLineNumber = normalizeLineNumber(finding.lineNumber);
    if (normalizedLineNumber !== undefined) {
        result.lineNumber = normalizedLineNumber;
    }

    return result;
}

/**
 * Normalize finding ID to ensure uniqueness and consistency
 */
function normalizeId(id: string): string {
    // Remove special characters and normalize format
    return id.replace(/[^a-zA-Z0-9\-_]/g, '-').toLowerCase();
}

/**
 * Normalize vulnerability type
 */
function normalizeType(type: string | VulnerabilityType): VulnerabilityType {
    if (typeof type === 'string') {
        const upperType = type.toUpperCase();

        // Map common variations to standard types
        const typeMap: Record<string, VulnerabilityType> = {
            'DEPENDENCY': VulnerabilityType.DEPENDENCY,
            'DEPS': VulnerabilityType.DEPENDENCY,
            'PACKAGE': VulnerabilityType.DEPENDENCY,

            'CODE': VulnerabilityType.CODE_VULNERABILITY,
            'CODE_VULNERABILITY': VulnerabilityType.CODE_VULNERABILITY,
            'SAST': VulnerabilityType.CODE_VULNERABILITY,

            'CONFIG': VulnerabilityType.CONFIGURATION,
            'CONFIGURATION': VulnerabilityType.CONFIGURATION,
            'SETTINGS': VulnerabilityType.CONFIGURATION,

            'SECRET': VulnerabilityType.SECRET_EXPOSURE,
            'SECRET_EXPOSURE': VulnerabilityType.SECRET_EXPOSURE,
            'CREDENTIAL': VulnerabilityType.SECRET_EXPOSURE,
            'API_KEY': VulnerabilityType.SECRET_EXPOSURE,

            'CRYPTO': VulnerabilityType.WEAK_CRYPTO,
            'WEAK_CRYPTO': VulnerabilityType.WEAK_CRYPTO,
            'CRYPTOGRAPHY': VulnerabilityType.WEAK_CRYPTO,

            'INJECTION': VulnerabilityType.INJECTION,
            'SQL_INJECTION': VulnerabilityType.INJECTION,
            'XSS': VulnerabilityType.INJECTION,
            'COMMAND_INJECTION': VulnerabilityType.INJECTION,

            'DESERIALIZATION': VulnerabilityType.INSECURE_DESERIALIZATION,
            'INSECURE_DESERIALIZATION': VulnerabilityType.INSECURE_DESERIALIZATION,
            'UNSAFE_DESERIALIZATION': VulnerabilityType.INSECURE_DESERIALIZATION
        };

        return typeMap[upperType] || VulnerabilityType.CODE_VULNERABILITY;
    }

    return type;
}

/**
 * Normalize severity level
 */
function normalizeSeverity(severity: string | SeverityLevel): SeverityLevel {
    if (typeof severity === 'string') {
        const upperSeverity = severity.toUpperCase();

        const severityMap: Record<string, SeverityLevel> = {
            'CRITICAL': SeverityLevel.CRITICAL,
            'BLOCKER': SeverityLevel.CRITICAL,
            'SEVERE': SeverityLevel.CRITICAL,

            'HIGH': SeverityLevel.HIGH,
            'MAJOR': SeverityLevel.HIGH,
            'IMPORTANT': SeverityLevel.HIGH,

            'MEDIUM': SeverityLevel.MEDIUM,
            'MODERATE': SeverityLevel.MEDIUM,
            'WARNING': SeverityLevel.MEDIUM,

            'LOW': SeverityLevel.LOW,
            'MINOR': SeverityLevel.LOW,
            'NOTE': SeverityLevel.LOW,

            'INFO': SeverityLevel.INFO,
            'INFORMATIONAL': SeverityLevel.INFO
        };

        return severityMap[upperSeverity] || SeverityLevel.MEDIUM;
    }

    return severity;
}

/**
 * Normalize CVE IDs
 */
function normalizeCVEIds(cveIds?: string[]): string[] {
    if (!cveIds || !Array.isArray(cveIds)) {
        return [];
    }

    return cveIds
        .filter(id => typeof id === 'string' && id.match(/^CVE-\d{4}-\d{4,}$/i))
        .map(id => id.toUpperCase())
        .filter((id, index, array) => array.indexOf(id) === index); // Remove duplicates
}

/**
 * Normalize component name
 */
function normalizeComponent(component?: string): string {
    if (!component) {
        return 'unknown';
    }

    // Clean up component name
    return component.trim().replace(/\s+/g, ' ');
}

/**
 * Normalize file path
 */
function normalizeFilePath(filePath?: string): string | undefined {
    if (!filePath) {
        return undefined;
    }

    // Normalize path separators and remove redundant elements
    return filePath
        .replace(/\\/g, '/')  // Convert Windows paths
        .replace(/\/+/g, '/') // Remove duplicate slashes
        .replace(/^\/+/, '')  // Remove leading slashes
        .trim();
}

/**
 * Normalize line number
 */
function normalizeLineNumber(lineNumber?: number): number | undefined {
    if (lineNumber === undefined || lineNumber === null) {
        return undefined;
    }

    const num = Number(lineNumber);
    return isNaN(num) || num < 1 ? undefined : Math.floor(num);
}

/**
 * Normalize title
 */
function normalizeTitle(title?: string): string {
    if (!title) {
        return 'Security vulnerability detected';
    }

    return title.trim().replace(/\s+/g, ' ');
}

/**
 * Normalize description
 */
function normalizeDescription(description?: string): string {
    if (!description) {
        return 'No description provided';
    }

    return description.trim().replace(/\s+/g, ' ');
}

/**
 * Normalize evidence array
 */
function normalizeEvidence(evidence: any[]): Evidence[] {
    if (!Array.isArray(evidence)) {
        return [];
    }

    return evidence
        .filter(item => item && typeof item === 'object' && item.type && item.content)
        .map(item => ({
            type: item.type,
            content: String(item.content).trim(),
            filePath: item.filePath ? normalizeFilePath(item.filePath) : undefined,
            lineRange: normalizeLineRange(item.lineRange) || [0, 0] as [number, number]
        }));
}

/**
 * Normalize line range
 */
function normalizeLineRange(lineRange?: [number, number]): [number, number] | undefined {
    if (!Array.isArray(lineRange) || lineRange.length !== 2) {
        return undefined;
    }

    const [start, end] = lineRange.map(n => Number(n));
    if (isNaN(start) || isNaN(end) || start < 1 || end < start) {
        return undefined;
    }

    return [Math.floor(start), Math.floor(end)];
}

/**
 * Normalize finding source
 */
function normalizeSource(source?: string | FindingSource): FindingSource {
    if (!source) {
        return FindingSource.CI_SECURITY;
    }

    if (typeof source === 'string') {
        const upperSource = source.toUpperCase();

        const sourceMap: Record<string, FindingSource> = {
            'DEPENDENCY': FindingSource.DEPENDENCY_SCANNER,
            'DEPENDENCY_SCANNER': FindingSource.DEPENDENCY_SCANNER,
            'DEPS': FindingSource.DEPENDENCY_SCANNER,

            'SAST': FindingSource.SAST_SCANNER,
            'SAST_SCANNER': FindingSource.SAST_SCANNER,
            'STATIC': FindingSource.SAST_SCANNER,

            'SECRET': FindingSource.SECRET_SCANNER,
            'SECRET_SCANNER': FindingSource.SECRET_SCANNER,
            'SECRETS': FindingSource.SECRET_SCANNER,

            'CONFIG': FindingSource.CONFIG_SCANNER,
            'CONFIG_SCAN': FindingSource.CONFIG_SCANNER,
            'CONFIG_SCANNER': FindingSource.CONFIG_SCANNER,

            'CI': FindingSource.CI_SECURITY,
            'CI_SECURITY': FindingSource.CI_SECURITY,
            'CI_REPORT': FindingSource.CI_SECURITY,
            'CD': FindingSource.CI_SECURITY,
            'BUILD': FindingSource.CI_SECURITY,

            'TEST': FindingSource.TEST
        };

        return sourceMap[upperSource] || FindingSource.CI_SECURITY;
    }

    return source;
}

/**
 * Normalize confidence score
 */
function normalizeConfidence(confidence?: number): number {
    if (confidence === undefined || confidence === null) {
        return 0.7; // Default confidence
    }

    const num = Number(confidence);
    if (isNaN(num)) {
        return 0.7;
    }

    // Clamp between 0.0 and 1.0
    return Math.max(0.0, Math.min(1.0, num));
}

/**
 * Normalize timestamp
 */
function normalizeTimestamp(timestamp?: string): string {
    if (!timestamp) {
        return new Date().toISOString();
    }

    try {
        return new Date(timestamp).toISOString();
    } catch (error) {
        console.warn('⚠️  Invalid timestamp format:', timestamp);
        return new Date().toISOString();
    }
}

/**
 * Validate that finding has all required fields
 */
function isValidFinding(finding: SecurityFinding): boolean {
    const required = [
        'id', 'type', 'severity', 'component',
        'title', 'description', 'source', 'confidence', 'detectedAt'
    ];

    for (const field of required) {
        if (!(field in finding) || finding[field as keyof SecurityFinding] === undefined) {
            console.warn(`⚠️  Finding missing required field: ${field}`);
            return false;
        }
    }

    // Validate confidence range
    if (finding.confidence < 0 || finding.confidence > 1) {
        console.warn(`⚠️  Invalid confidence score: ${finding.confidence}`);
        return false;
    }

    // Validate line number if present
    if (finding.lineNumber !== undefined && finding.lineNumber < 1) {
        console.warn(`⚠️  Invalid line number: ${finding.lineNumber}`);
        return false;
    }

    return true;
}

/**
 * Get statistics about normalization process
 */
export function getNormalizationStats(before: SecurityFinding[], after: SecurityFinding[]): {
    inputCount: number;
    outputCount: number;
    filteredCount: number;
    typeDistribution: Record<string, number>;
    severityDistribution: Record<string, number>;
    sourceDistribution: Record<string, number>;
} {
    const typeDistribution: Record<string, number> = {};
    const severityDistribution: Record<string, number> = {};
    const sourceDistribution: Record<string, number> = {};

    for (const finding of after) {
        typeDistribution[finding.type] = (typeDistribution[finding.type] || 0) + 1;
        severityDistribution[finding.severity] = (severityDistribution[finding.severity] || 0) + 1;
        sourceDistribution[finding.source] = (sourceDistribution[finding.source] || 0) + 1;
    }

    return {
        inputCount: before.length,
        outputCount: after.length,
        filteredCount: before.length - after.length,
        typeDistribution,
        severityDistribution,
        sourceDistribution
    };
}
