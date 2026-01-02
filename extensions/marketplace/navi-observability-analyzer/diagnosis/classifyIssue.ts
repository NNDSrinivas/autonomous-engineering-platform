/**
 * Issue Classification for NAVI Observability & Metrics Analyzer
 * 
 * This module classifies correlated signals into structured issues
 * for business impact assessment and remediation planning.
 */

import {
    ClassifiedIssue,
    CorrelatedSignal,
    Evidence,
    HealthStatus,
    IssueType,
    RootCause,
    SeverityLevel,
    TechnicalDetails
} from '../types';

/**
 * Classify correlated data into a structured issue
 * @param correlatedData Correlated observability signals
 * @returns Classified issue or null if not significant enough
 */
export async function classifyIssue(correlatedData: any): Promise<ClassifiedIssue | null> {
    if (!correlatedData || !correlatedData.signals) {
        return null;
    }

    // Basic classification based on signal types and confidence
    const confidence = typeof correlatedData.confidence === 'number' ? correlatedData.confidence : 0.5;
    
    if (confidence < 0.3) {
        return null; // Not confident enough to classify as an issue
    }

    const correlatedSignals = buildCorrelatedSignals(correlatedData, confidence);
    const technicalDetails = buildTechnicalDetails(correlatedData.technicalDetails);
    const rootCause = buildRootCause(correlatedData.rootCause, confidence);

    const issue: ClassifiedIssue = {
        id: correlatedData.id || `issue-${Date.now()}`,
        type: coerceIssueType(correlatedData.type),
        title: correlatedData.title || correlatedData.description || 'Observability Issue Detected',
        severity: coerceSeverity(correlatedData.severity, confidence),
        confidence,
        affectedServices: Array.isArray(correlatedData.affectedServices) ? correlatedData.affectedServices : ['unknown'],
        startTime: typeof correlatedData.startTime === 'number' ? correlatedData.startTime : Date.now(),
        businessImpact: correlatedData.businessImpact || 'Unknown impact',
        technicalDetails,
        correlatedSignals
    };

    if (typeof correlatedData.endTime === 'number') {
        issue.endTime = correlatedData.endTime;
    }

    if (rootCause) {
        issue.rootCause = rootCause;
    }

    return issue;
}

function coerceIssueType(value: unknown): IssueType {
    if (typeof value === 'string' && Object.values(IssueType).includes(value as IssueType)) {
        return value as IssueType;
    }
    return IssueType.PERFORMANCE_DEGRADATION;
}

function coerceSeverity(value: unknown, confidence: number): SeverityLevel {
    if (typeof value === 'string' && Object.values(SeverityLevel).includes(value as SeverityLevel)) {
        return value as SeverityLevel;
    }
    return confidence > 0.8 ? SeverityLevel.HIGH : SeverityLevel.MEDIUM;
}

function buildCorrelatedSignals(raw: any, confidence: number): CorrelatedSignal[] {
    if (Array.isArray(raw?.signals) && raw.signals.length > 0) {
        return raw.signals.map((signal: any) => ({
            source: typeof signal?.source === 'string' ? signal.source : String(raw.source || 'correlation'),
            type: signal?.type === 'log' || signal?.type === 'trace' ? signal.type : 'metric',
            correlation: typeof signal?.correlation === 'number' ? signal.correlation : confidence,
            timeOffset: typeof signal?.timeOffset === 'number' ? signal.timeOffset : 0,
            description: typeof signal?.description === 'string' ? signal.description : String(signal)
        }));
    }

    return [{
        source: String(raw?.source || 'correlation'),
        type: 'metric',
        correlation: confidence,
        timeOffset: 0,
        description: raw?.description ? String(raw.description) : 'Correlated signal detected'
    }];
}

function buildTechnicalDetails(raw: any): TechnicalDetails {
    return {
        affectedComponents: raw?.affectedComponents ?? [],
        errorPatterns: raw?.errorPatterns ?? [],
        performanceMetrics: raw?.performanceMetrics ?? {},
        systemHealth: raw?.systemHealth ?? {
            cpu: 0,
            memory: 0,
            disk: 0,
            network: 0,
            overall: HealthStatus.DEGRADED
        }
    };
}

function buildRootCause(raw: any, confidence: number): RootCause | undefined {
    if (!raw) {
        return undefined;
    }

    if (typeof raw === 'object' && 'hypothesis' in raw) {
        const evidence = Array.isArray((raw as RootCause).evidence) ? (raw as RootCause).evidence : [];
        return {
            hypothesis: String((raw as RootCause).hypothesis),
            confidence: typeof (raw as RootCause).confidence === 'number' ? (raw as RootCause).confidence : confidence,
            evidence: evidence as Evidence[],
            timeToDetection: typeof (raw as RootCause).timeToDetection === 'number' ? (raw as RootCause).timeToDetection : 0
        };
    }

    return {
        hypothesis: String(raw),
        confidence,
        evidence: [],
        timeToDetection: 0
    };
}
