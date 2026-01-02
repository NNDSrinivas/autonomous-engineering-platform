/**
 * Dependency Fix Proposals
 * 
 * Generates fix proposals for dependency vulnerabilities including
 * version upgrades, security patches, and alternative packages.
 */

import { SecurityFinding, RemediationProposal, RemediationType, VulnerabilityType } from '../types';
import * as semver from 'semver';

/**
 * Known vulnerable packages with recommended fixes
 */
const VULNERABILITY_FIXES = {
    // Express.js vulnerabilities
    'express': {
        '4.17.0': { fixVersion: '4.18.2', cve: ['CVE-2022-24999'] },
        '4.16.4': { fixVersion: '4.18.2', cve: ['CVE-2022-24999'] },
        '4.15.5': { fixVersion: '4.18.2', cve: ['CVE-2022-24999'] }
    },

    // Lodash vulnerabilities
    'lodash': {
        '4.17.20': { fixVersion: '4.17.21', cve: ['CVE-2021-23337'] },
        '4.17.19': { fixVersion: '4.17.21', cve: ['CVE-2021-23337'] },
        '4.17.15': { fixVersion: '4.17.21', cve: ['CVE-2019-10744', 'CVE-2020-8203'] }
    },

    // React vulnerabilities
    'react': {
        '16.13.1': { fixVersion: '18.2.0', cve: ['CVE-2021-44906'] },
        '17.0.1': { fixVersion: '18.2.0', cve: ['CVE-2021-44906'] }
    },

    // Node.js crypto vulnerabilities
    'crypto-js': {
        '3.1.8': { fixVersion: '4.1.1', cve: ['CVE-2023-46233'] },
        '4.0.0': { fixVersion: '4.1.1', cve: ['CVE-2023-46233'] }
    },

    // axios vulnerabilities
    'axios': {
        '0.21.1': { fixVersion: '0.28.0', cve: ['CVE-2022-1214'] },
        '0.21.0': { fixVersion: '0.28.0', cve: ['CVE-2022-1214'] }
    },

    // moment.js vulnerabilities (recommend day.js alternative)
    'moment': {
        '*': {
            alternative: 'dayjs',
            reason: 'Moment.js is in maintenance mode, Day.js offers better performance and security',
            cve: ['CVE-2022-24785', 'CVE-2022-31129']
        }
    }
};

/**
 * Generate dependency fix proposals
 */
export function generateDependencyFixes(findings: SecurityFinding[]): RemediationProposal[] {
    console.log(`🔧 Generating dependency fixes for ${findings.length} findings...`);

    const dependencyFindings = findings.filter(f => f.type === VulnerabilityType.DEPENDENCY);
    const proposals: RemediationProposal[] = [];

    for (const finding of dependencyFindings) {
        const proposal = createDependencyFixProposal(finding);
        if (proposal) {
            proposals.push(proposal);
        }
    }

    console.log(`✅ Generated ${proposals.length} dependency fix proposals`);
    return proposals;
}

/**
 * Create individual dependency fix proposal
 */
function createDependencyFixProposal(finding: SecurityFinding): RemediationProposal | null {
    const packageName = extractPackageName(finding);
    const currentVersion = extractCurrentVersion(finding);

    if (!packageName) {
        console.warn(`⚠️ Could not extract package info from finding: ${finding.title}`);
        return null;
    }

    // Check for known fixes
    const knownFix = getKnownFix(packageName, currentVersion ?? undefined);
    if (knownFix) {
        return createKnownFixProposal(finding, packageName, currentVersion ?? '*', knownFix);
    }

    if (!currentVersion) {
        console.warn(`⚠️ Could not extract package version from finding: ${finding.title}`);
        return null;
    }

    // Generate generic version upgrade proposal
    return createGenericUpgradeProposal(finding, packageName, currentVersion);
}

/**
 * Extract package name from finding
 */
function extractPackageName(finding: SecurityFinding): string | null {
    // Try component field first
    if (finding.component && finding.component !== 'Unknown') {
        return finding.component;
    }

    // Parse from title or description
    const text = `${finding.title} ${finding.description}`;
    const packagePatterns = [
        /package[:\s]+([a-z0-9\-_./@]+)/i,
        /dependency[:\s]+([a-z0-9\-_./@]+)/i,
        /module[:\s]+([a-z0-9\-_./@]+)/i,
        /library[:\s]+([a-z0-9\-_./@]+)/i,
        /'([a-z0-9\-_./@]+)'\s+package/i,
        /"([a-z0-9\-_./@]+)"\s+package/i
    ];

    for (const pattern of packagePatterns) {
        const match = text.match(pattern);
        if (match && match[1]) {
            return match[1];
        }
    }

    return null;
}

/**
 * Extract current version from finding
 */
function extractCurrentVersion(finding: SecurityFinding): string | null {
    const text = `${finding.title} ${finding.description}`;
    const versionPatterns = [
        /version[:\s]+([0-9]+\.[0-9]+\.[0-9]+[a-z0-9\-.]*)/i,
        /v([0-9]+\.[0-9]+\.[0-9]+[a-z0-9\-.]*)/i,
        /([0-9]+\.[0-9]+\.[0-9]+[a-z0-9\-.]*)\s*vulnerable/i,
        /@([0-9]+\.[0-9]+\.[0-9]+[a-z0-9\-.]*)/i
    ];

    for (const pattern of versionPatterns) {
        const match = text.match(pattern);
        if (match && match[1] && semver.valid(match[1])) {
            return match[1];
        }
    }

    return null;
}

/**
 * Get known fix information
 */
function getKnownFix(packageName: string, currentVersion?: string) {
    const packageFixes = VULNERABILITY_FIXES[packageName as keyof typeof VULNERABILITY_FIXES];
    if (!packageFixes) return null;

    // Cast to any for dynamic indexing since TypeScript can't handle the complex union type
    const fixes = packageFixes as any;

    // Check for exact version match
    if (currentVersion && fixes[currentVersion]) {
        return fixes[currentVersion];
    }

    // Check for wildcard match
    if (fixes['*']) {
        return fixes['*'];
    }

    if (!currentVersion) {
        return null;
    }

    // Check for version range matches
    for (const [versionRange, fix] of Object.entries(fixes)) {
        if (versionRange !== '*' && semver.satisfies(currentVersion, `<=${versionRange}`)) {
            return fix;
        }
    }

    return null;
}

/**
 * Create proposal for known fixes
 */
function createKnownFixProposal(
    _finding: SecurityFinding,
    packageName: string,
    currentVersion: string,
    fix: any
): RemediationProposal {
    if (fix.alternative) {
        return {
            type: RemediationType.DEPENDENCY_REPLACEMENT,
            description: `Replace ${packageName} with ${fix.alternative}`,
            confidence: 0.9,
            effort: determineReplacementEffort(packageName),
            risk: 'MEDIUM',
            changes: [{
                filePath: 'package.json',
                changeType: 'DEPENDENCY_REPLACEMENT',
                currentValue: `"${packageName}": "${currentVersion}"`,
                proposedValue: `"${fix.alternative}": "latest"`,
                lineNumber: 0 // Will be determined during application
            }],
            explanation: fix.reason || `Replace vulnerable ${packageName}@${currentVersion} with secure alternative ${fix.alternative}`,
            cveIds: fix.cve || [],
            testing: {
                required: true,
                suggestions: [
                    'Run existing test suite',
                    'Test core functionality that uses date/time operations',
                    'Verify build process completes successfully'
                ]
            },
            rollback: {
                procedure: `Revert package.json and run npm install to restore ${packageName}@${currentVersion}`,
                verification: 'Verify application functionality is restored'
            }
        };
    } else {
        return {
            type: RemediationType.DEPENDENCY_UPDATE,
            description: `Update ${packageName} from ${currentVersion} to ${fix.fixVersion}`,
            confidence: 0.95,
            effort: determineUpdateEffort(currentVersion, fix.fixVersion),
            risk: 'LOW',
            changes: [{
                filePath: 'package.json',
                changeType: 'DEPENDENCY_UPDATE',
                currentValue: `"${packageName}": "${currentVersion}"`,
                proposedValue: `"${packageName}": "${fix.fixVersion}"`,
                lineNumber: 0
            }],
            explanation: `Update ${packageName} to version ${fix.fixVersion} to fix security vulnerabilities`,
            cveIds: fix.cve || [],
            testing: {
                required: true,
                suggestions: [
                    'Run existing test suite',
                    'Test functionality that depends on this package',
                    'Verify no breaking changes in API usage'
                ]
            },
            rollback: {
                procedure: `Update package.json to ${packageName}@${currentVersion} and run npm install`,
                verification: 'Verify application functionality is restored'
            }
        };
    }
}

/**
 * Create generic upgrade proposal
 */
function createGenericUpgradeProposal(
    finding: SecurityFinding,
    packageName: string,
    currentVersion: string
): RemediationProposal {
    const suggestedVersion = suggestSafeVersion(currentVersion);

    return {
        type: RemediationType.DEPENDENCY_UPDATE,
        description: `Update ${packageName} to address security vulnerability`,
        confidence: 0.7,
        effort: determineUpdateEffort(currentVersion, suggestedVersion),
        risk: 'MEDIUM',
        changes: [{
            filePath: 'package.json',
            changeType: 'DEPENDENCY_UPDATE',
            currentValue: `"${packageName}": "${currentVersion}"`,
            proposedValue: `"${packageName}": "${suggestedVersion}"`,
            lineNumber: 0
        }],
        explanation: `Update ${packageName} from vulnerable version ${currentVersion}. Please verify the latest secure version before applying.`,
        cveIds: finding.cveIds || [],
        testing: {
            required: true,
            suggestions: [
                'Check package changelog for breaking changes',
                'Run comprehensive test suite',
                'Manually test functionality that uses this package',
                'Verify integration points are not affected'
            ]
        },
        rollback: {
            procedure: `Revert package.json to ${packageName}@${currentVersion} and run npm install`,
            verification: 'Verify application functionality is restored'
        }
    };
}

/**
 * Suggest a safer version based on current version
 */
function suggestSafeVersion(currentVersion: string): string {
    const parsed = semver.parse(currentVersion);
    if (!parsed) return 'latest';

    // Suggest next minor version for better compatibility
    return `${parsed.major}.${parsed.minor + 1}.0`;
}

/**
 * Determine effort level for package replacement
 */
function determineReplacementEffort(packageName: string): RemediationProposal['effort'] {
    const highEffortPackages = [
        'moment', 'lodash', 'jquery', 'axios', 'request'
    ];

    const mediumEffortPackages = [
        'express', 'react', 'vue', 'angular'
    ];

    if (highEffortPackages.includes(packageName)) {
        return 'HIGH';
    } else if (mediumEffortPackages.includes(packageName)) {
        return 'MEDIUM';
    } else {
        return 'LOW';
    }
}

/**
 * Determine effort level for version update
 */
function determineUpdateEffort(currentVersion: string, newVersion: string): RemediationProposal['effort'] {
    if (!semver.valid(currentVersion) || !semver.valid(newVersion)) {
        return 'MEDIUM';
    }

    const currentParsed = semver.parse(currentVersion);
    const newParsed = semver.parse(newVersion);

    if (!currentParsed || !newParsed) return 'MEDIUM';

    // Major version change = high effort
    if (newParsed.major > currentParsed.major) {
        return 'HIGH';
    }

    // Minor version change = medium effort
    if (newParsed.minor > currentParsed.minor) {
        return 'MEDIUM';
    }

    // Patch version change = low effort
    return 'LOW';
}
