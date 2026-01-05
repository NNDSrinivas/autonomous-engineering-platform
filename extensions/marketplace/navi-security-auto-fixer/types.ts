/**
 * NAVI Security Vulnerability Auto-Fixer Extension Types
 * 
 * Production-grade type definitions for enterprise security automation.
 * This extension demonstrates NAVI's ability to surpass Copilot/Cline in 
 * enterprise trust, security, and real-world usefulness.
 */

// Extension Context & Configuration

export interface ExtensionContext {
    /** Repository interface for reading code and configurations */
    repo: RepositoryAPI;

    /** CI/CD integration interface */
    ci: CISecurityAPI;

    /** Extension configuration */
    config: SecurityConfig;

    /** Approval workflow interface */
    approval: ApprovalAPI;

    /** NAVI workspace interface */
    workspace: WorkspaceAPI;
}

export interface RepositoryAPI {
    /** Get dependency graph with vulnerability data */
    dependencyGraph(): Promise<Dependency[]>;

    /** Read file content */
    readFile(path: string): Promise<string>;

    /** List files matching pattern */
    listFiles(pattern: string): Promise<string[]>;

    /** Get repository metadata */
    getMetadata(): Promise<RepoMetadata>;
}

export interface CISecurityAPI {
    /** Read security scan results from CI */
    getSecurityReports(): Promise<CISecurityReport[]>;

    /** Get latest build information */
    getLatestBuild(): Promise<BuildInfo>;
}

export interface SecurityConfig {
    /** Maximum severity level to auto-fix */
    autoFixThreshold: SeverityLevel;

    /** Confidence threshold for auto-remediation */
    confidenceThreshold: number;

    /** Enable dependency vulnerability scanning */
    scanDependencies: boolean;

    /** Enable static analysis security testing */
    enableSAST: boolean;

    /** Enable secret scanning */
    scanSecrets: boolean;

    /** Auto-approve fixes with confidence above this threshold */
    autoApprove?: boolean;

    /** Enabled scanners */
    enabledScanners?: string[];

    /** Paths to exclude from scanning */
    excludePaths?: string[];
}

export interface ApprovalAPI {
    /** Request approval for proposed fixes */
    requestApproval(proposal: RemediationProposal): Promise<ApprovalResult>;
}

export interface WorkspaceAPI {
    /** Read workspace files */
    readFile(path: string): Promise<string>;

    /** Get workspace root */
    getRoot(): Promise<string>;
}

// Vulnerability Types

export enum VulnerabilityType {
    DEPENDENCY = 'DEPENDENCY',
    CODE_VULNERABILITY = 'CODE_VULNERABILITY',
    CONFIGURATION = 'CONFIGURATION',
    SECRET_EXPOSURE = 'SECRET_EXPOSURE',
    WEAK_CRYPTO = 'WEAK_CRYPTO',
    INJECTION = 'INJECTION',
    INSECURE_DESERIALIZATION = 'INSECURE_DESERIALIZATION'
}

export enum SeverityLevel {
    CRITICAL = 'CRITICAL',
    HIGH = 'HIGH',
    MEDIUM = 'MEDIUM',
    LOW = 'LOW',
    INFO = 'INFO'
}

export enum RemediationType {
    DEPENDENCY_UPDATE = 'DEPENDENCY_UPDATE',
    DEPENDENCY_REPLACEMENT = 'DEPENDENCY_REPLACEMENT',
    CONFIGURATION_UPDATE = 'CONFIGURATION_UPDATE',
    CODE_CHANGE = 'CODE_CHANGE',
    MITIGATION = 'MITIGATION'
}

export interface ProposedChange {
    filePath: string;
    changeType: 'DEPENDENCY_UPDATE' | 'DEPENDENCY_REPLACEMENT' | 'CONFIGURATION_UPDATE' | 'CONFIGURATION_ADDITION' | 'CODE_REPLACEMENT' | 'CODE_ADDITION' | 'CODE_UPDATE';
    currentValue: string;
    proposedValue: string;
    lineNumber: number;
}

export interface SecurityFinding {
    /** Unique identifier for this finding */
    id: string;

    /** Type of vulnerability */
    type: VulnerabilityType;

    /** Severity level */
    severity: SeverityLevel;

    /** CVE identifiers if applicable */
    cveIds?: string[];

    /** Affected component or dependency */
    component: string;

    /** File path where vulnerability exists */
    filePath?: string;

    /** Line number if applicable */
    lineNumber?: number;

    /** Vulnerability title */
    title: string;

    /** Detailed description */
    description: string;

    /** Evidence supporting this finding */
    evidence?: Evidence[];

    /** Source of this finding */
    source: FindingSource | string;

    /** Confidence score (0.0 - 1.0) */
    confidence: number;

    /** When this finding was detected */
    detectedAt?: string;
}

export interface Evidence {
    /** Type of evidence */
    type: 'CODE_PATTERN' | 'DEPENDENCY_VERSION' | 'CONFIG_VALUE' | 'CI_REPORT';

    /** Evidence content */
    content: string;

    /** File path if relevant */
    filePath?: string | undefined;

    /** Line range if relevant */
    lineRange?: [number, number];
}

export enum FindingSource {
    DEPENDENCY_SCANNER = 'DEPENDENCY_SCANNER',
    SAST_SCANNER = 'SAST_SCANNER',
    SECRET_SCANNER = 'SECRET_SCANNER',
    CONFIG_SCANNER = 'CONFIG_SCANNER',
    CI_SECURITY = 'CI_SECURITY',
    TEST = 'TEST'
}

// Dependencies and CI Data

export interface Dependency {
    /** Package name */
    name: string;

    /** Current version */
    version: string;

    /** Package manager ecosystem */
    ecosystem: 'npm' | 'pip' | 'maven' | 'nuget' | 'composer' | 'rubygems';

    /** Known CVE vulnerabilities */
    cve?: CVEVulnerability[];

    /** Latest available version */
    latestVersion?: string;

    /** Direct or transitive dependency */
    direct: boolean;

    /** File where dependency is declared */
    manifestFile: string;
}

export interface CVEVulnerability {
    /** CVE identifier */
    id: string;

    /** CVSS score */
    score: number;

    /** Vulnerability summary */
    summary: string;

    /** Affected version range */
    affectedVersions: string;

    /** Patched version */
    patchedVersion?: string;

    /** Severity level */
    severity: SeverityLevel;
}

export interface CISecurityReport {
    /** Report source/tool */
    source: string;

    /** Report timestamp */
    timestamp: string;

    /** Security findings */
    findings: SecurityFinding[];

    /** Report metadata */
    metadata: {
        buildId?: string;
        commitSha?: string;
        branch?: string;
    };
}

// Fix Proposals and Remediation

export interface RemediationProposal {
    type: RemediationType;
    description: string;
    confidence: number;
    effort: 'LOW' | 'MEDIUM' | 'HIGH';
    risk: 'LOW' | 'MEDIUM' | 'HIGH';
    changes: ProposedChange[];
    explanation: string;
    cveIds?: string[];
    testing: {
        required: boolean;
        suggestions: string[];
    };
    rollback: {
        procedure: string;
        verification: string;
    };
}

export interface RemediationAction {
    /** Type of action */
    type: ActionType;

    /** Human-readable description */
    description: string;

    /** File to modify */
    filePath?: string;

    /** Specific changes to make */
    changes?: FileChange[];

    /** Command to execute */
    command?: string;

    /** Whether this action is safe */
    safe: boolean;

    /** Whether this action is reversible */
    reversible: boolean;

    /** Risk assessment */
    riskLevel: 'LOW' | 'MEDIUM' | 'HIGH';
}

export enum ActionType {
    UPDATE_DEPENDENCY = 'UPDATE_DEPENDENCY',
    PATCH_CODE = 'PATCH_CODE',
    UPDATE_CONFIG = 'UPDATE_CONFIG',
    ADD_SECURITY_HEADER = 'ADD_SECURITY_HEADER',
    REPLACE_WEAK_CRYPTO = 'REPLACE_WEAK_CRYPTO',
    REMOVE_SECRET = 'REMOVE_SECRET',
    ADD_INPUT_VALIDATION = 'ADD_INPUT_VALIDATION'
}

export interface FileChange {
    /** Line number to change */
    lineNumber: number;

    /** Original content */
    originalContent: string;

    /** Replacement content */
    newContent: string;

    /** Change description */
    description: string;
}

// Analysis and Classification

export interface VulnerabilityExplanation {
    /** Summary for humans */
    humanSummary: string;

    /** Technical details */
    technicalDetails: string;

    /** Impact assessment */
    impact: string;

    /** Why this matters */
    businessImpact: string;

    /** Recommended action */
    recommendedAction: string;

    /** Additional resources */
    references?: string[];
}

export interface RiskAssessment {
    /** Overall risk score (0.0 - 1.0) */
    riskScore: number;

    /** Exploitability score */
    exploitability: number;

    /** Impact score */
    impact: number;

    /** Likelihood of exploitation */
    likelihood: 'LOW' | 'MEDIUM' | 'HIGH';

    /** Business criticality */
    businessCriticality: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
}

// Extension Results

export interface SecurityAnalysisResult {
    /** All security findings */
    findings: SecurityFinding[];

    /** Summary of analysis */
    summary: {
        totalFindings: number;
        criticalCount: number;
        highCount: number;
        mediumCount: number;
        lowCount: number;
    };

    /** Proposed fixes */
    proposals: RemediationProposal[];

    /** Overall risk assessment */
    riskAssessment: RiskAssessment;

    /** Whether approval is required */
    requiresApproval: boolean;

    /** Human-readable recommendations */
    recommendations: string[];

    /** Analysis metadata */
    metadata: {
        analysisTime: string;
        extensionVersion: string;
        confidence: number;
    };
}

// Utility Types

export interface RepoMetadata {
    /** Repository name */
    name: string;

    /** Primary language */
    language: string;

    /** Branch being analyzed */
    branch: string;

    /** Commit SHA */
    commitSha: string;

    /** Repository size metrics */
    size: {
        files: number;
        lines: number;
    };
}

export interface BuildInfo {
    /** Build ID */
    id: string;

    /** Status */
    status: 'SUCCESS' | 'FAILURE' | 'IN_PROGRESS';

    /** Commit SHA */
    commitSha: string;

    /** Build timestamp */
    timestamp: string;
}

export interface ApprovalResult {
    /** Whether approved */
    approved: boolean;

    /** Reason for decision */
    reason?: string;

    /** Rollback token */
    rollbackToken?: string;

    /** Approver information */
    approver?: string;

    /** Approval timestamp */
    approvedAt?: string;
}
