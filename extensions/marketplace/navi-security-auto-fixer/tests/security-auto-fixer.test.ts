/**
 * Comprehensive Test Suite for Security Auto-Fixer Extension
 * 
 * Tests all components including scanners, analysis, and fix proposals
 * with real vulnerability scenarios and edge cases.
 */

import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';
import {
    ExtensionContext,
    SecurityConfig,
    SecurityFinding,
    SeverityLevel,
    VulnerabilityType,
    RemediationType,
    FindingSource,
    RepositoryAPI,
    CISecurityAPI,
    CISecurityReport,
    ApprovalAPI,
    WorkspaceAPI,
    Dependency
} from '../types';

// Import modules to test
import { scanDependencies } from '../scanners/dependencyScanner';
import { scanWithSAST } from '../scanners/sastScanner';
import { scanSecrets } from '../scanners/secretScanner';
import { readCISecurityReports } from '../scanners/ciSecurityReader';
import { normalizeFindings } from '../analysis/normalizeFindings';
import { classifySeverity } from '../analysis/classifySeverity';
import { deduplicateFindings } from '../analysis/dedupe';
import { assessRisk } from '../analysis/riskAssessment';
import { generateDependencyFixes } from '../fixes/dependencyFixes';
import { generateConfigFixes } from '../fixes/configFixes';
import { generateCodeFixes } from '../fixes/codeFixes';

type MockFile = { path: string; content: string };

const defaultConfig: SecurityConfig = {
    autoFixThreshold: SeverityLevel.MEDIUM,
    confidenceThreshold: 0.8,
    scanDependencies: true,
    enableSAST: true,
    scanSecrets: true,
    autoApprove: false,
    enabledScanners: ['dependency', 'sast', 'secrets', 'ci'],
    excludePaths: ['node_modules/', 'test/', '.git/']
};

const buildDependenciesFromPackageJson = (files: MockFile[]): Dependency[] => {
    const packageFile = files.find(file => file.path === 'package.json');
    if (!packageFile) {
        return [];
    }

    try {
        const json = JSON.parse(packageFile.content) as {
            dependencies?: Record<string, string>;
            devDependencies?: Record<string, string>;
        };
        const dependencies = { ...json.dependencies, ...json.devDependencies };

        return Object.entries(dependencies).map(([name, version]) => ({
            name,
            version: String(version),
            ecosystem: 'npm',
            direct: true,
            manifestFile: 'package.json'
        }));
    } catch {
        return [];
    }
};

const createMockRepo = (files: MockFile[]): RepositoryAPI => ({
    async dependencyGraph() {
        return buildDependenciesFromPackageJson(files);
    },
    async readFile(path: string) {
        const file = files.find(entry => entry.path === path);
        if (!file) {
            throw new Error(`File not found: ${path}`);
        }
        return file.content;
    },
    async listFiles(pattern: string) {
        const matches = new Set<string>();
        const extensionMatch = pattern.match(/\*\.([a-z0-9*]+)$/i);
        const wantsEnv = pattern.includes('*.env');
        const wantsConfig = pattern.includes('config.');
        const wantsSettings = pattern.includes('settings.');

        for (const file of files) {
            const lowerPath = file.path.toLowerCase();

            if (wantsEnv && lowerPath.includes('.env')) {
                matches.add(file.path);
                continue;
            }
            if (wantsConfig && lowerPath.includes('config.')) {
                matches.add(file.path);
                continue;
            }
            if (wantsSettings && lowerPath.includes('settings.')) {
                matches.add(file.path);
                continue;
            }

            if (extensionMatch) {
                const ext = extensionMatch[1].replace('*', '');
                if (ext && lowerPath.endsWith(`.${ext}`)) {
                    matches.add(file.path);
                }
            }
        }

        return Array.from(matches.values());
    },
    async getMetadata() {
        const lineCount = files.reduce((sum, file) => sum + file.content.split('\n').length, 0);
        return {
            name: 'test-repo',
            language: 'typescript',
            branch: 'main',
            commitSha: 'test-sha',
            size: {
                files: files.length,
                lines: lineCount
            }
        };
    }
});

const createMockCI = (reports: CISecurityReport[]): CISecurityAPI => ({
    async getSecurityReports() {
        return reports;
    },
    async getLatestBuild() {
        return {
            id: 'build-001',
            status: 'SUCCESS',
            commitSha: 'test-sha',
            timestamp: new Date().toISOString()
        };
    }
});

const createMockApproval = (): ApprovalAPI => ({
    async requestApproval() {
        return { approved: true };
    }
});

const createMockWorkspace = (files: MockFile[]): WorkspaceAPI => ({
    async readFile(path: string) {
        const file = files.find(entry => entry.path === path);
        if (!file) {
            throw new Error(`Workspace file not found: ${path}`);
        }
        return file.content;
    },
    async getRoot() {
        return '/test/repo';
    }
});

const createMockContext = (
    files: MockFile[],
    configOverrides: Partial<SecurityConfig> = {},
    ciReports: CISecurityReport[] = []
): ExtensionContext => ({
    repo: createMockRepo(files),
    ci: createMockCI(ciReports),
    approval: createMockApproval(),
    workspace: createMockWorkspace(files),
    config: { ...defaultConfig, ...configOverrides }
});

describe('Security Auto-Fixer Extension', () => {
    let mockContext: ExtensionContext;
    let mockFiles: MockFile[];

    beforeEach(() => {
        // Mock context for each test
        mockFiles = [
            { path: 'package.json', content: '{"dependencies": {"express": "4.16.4", "lodash": "4.17.15"}}' },
            { path: 'server.js', content: 'const express = require("express");\napp.get("/user/:id", (req, res) => {\n  db.query("SELECT * FROM users WHERE id = " + req.params.id);\n});' },
            { path: '.env', content: 'DATABASE_URL=postgresql://user:password123@localhost:5432/db\nAPI_KEY=abc123def456\nDEBUG=true' }
        ];
        mockContext = createMockContext(mockFiles);

        // Clear console logs for clean test output
        jest.spyOn(console, 'log').mockImplementation(() => { });
        jest.spyOn(console, 'warn').mockImplementation(() => { });
        jest.spyOn(console, 'error').mockImplementation(() => { });
    });

    afterEach(() => {
        jest.restoreAllMocks();
    });

    describe('Dependency Scanner', () => {
        it('should detect known vulnerable dependencies', async () => {
            const findings = await scanDependencies(mockContext.repo);

            expect(findings).toHaveLength(2); // express and lodash vulnerabilities

            const expressVuln = findings.find(f => f.component === 'express');
            expect(expressVuln).toBeDefined();
            expect(expressVuln!.severity).toBe(SeverityLevel.HIGH);
            expect(expressVuln!.cveIds).toContain('CVE-2022-24999');

            const lodashVuln = findings.find(f => f.component === 'lodash');
            expect(lodashVuln).toBeDefined();
            expect(lodashVuln!.severity).toBe(SeverityLevel.MEDIUM);
            expect(lodashVuln!.cveIds).toContain('CVE-2019-10744');
        });

        it('should handle empty package.json gracefully', async () => {
            const emptyContext = createMockContext([{ path: 'package.json', content: '{}' }]);

            const findings = await scanDependencies(emptyContext.repo);
            expect(findings).toHaveLength(0);
        });

        it('should handle malformed package.json', async () => {
            const badContext = createMockContext([{ path: 'package.json', content: '{ invalid json' }]);

            const findings = await scanDependencies(badContext.repo);
            expect(findings).toHaveLength(0);
        });
    });

    describe('SAST Scanner', () => {
        it('should detect SQL injection vulnerabilities', async () => {
            const findings = await scanWithSAST(mockContext.repo);

            const sqlInjectionVuln = findings.find(f =>
                f.type === VulnerabilityType.INJECTION &&
                f.title.includes('SQL Injection')
            );

            expect(sqlInjectionVuln).toBeDefined();
            expect(sqlInjectionVuln!.severity).toBe(SeverityLevel.HIGH);
            expect(sqlInjectionVuln!.filePath).toBe('server.js');
            expect(sqlInjectionVuln!.lineNumber).toBe(3);
            expect(sqlInjectionVuln!.confidence).toBeGreaterThan(0.8);
        });

        it('should detect weak cryptography patterns', async () => {
            const cryptoContext = createMockContext([
                ...mockFiles,
                {
                    path: 'crypto.js',
                    content: 'const hash = crypto.createHash("md5").update(password).digest("hex");'
                }
            ]);

            const findings = await scanWithSAST(cryptoContext.repo);
            const cryptoVuln = findings.find(f => f.title.includes('Weak Cryptographic Hash'));

            expect(cryptoVuln).toBeDefined();
            expect(cryptoVuln!.severity).toBe(SeverityLevel.MEDIUM);
            expect(cryptoVuln!.type).toBe(VulnerabilityType.WEAK_CRYPTO);
        });

        it('should not flag secure code patterns', async () => {
            const secureContext = createMockContext([{
                path: 'secure.js',
                content: 'const stmt = db.prepare("SELECT * FROM users WHERE id = ?");\nstmt.get(userId);'
            }]);

            const findings = await scanWithSAST(secureContext.repo);
            expect(findings).toHaveLength(0);
        });
    });

    describe('Secret Scanner', () => {
        it('should detect exposed secrets in environment files', async () => {
            const findings = await scanSecrets(mockContext.repo);

            expect(findings.length).toBeGreaterThan(0);

            const apiKeySecret = findings.find(f => f.title.includes('API Key'));
            expect(apiKeySecret).toBeDefined();
            expect(apiKeySecret!.severity).toBe(SeverityLevel.HIGH);
            expect(apiKeySecret!.type).toBe(VulnerabilityType.SECRET_EXPOSURE);
            expect(apiKeySecret!.filePath).toBe('.env');
        });

        it('should handle false positives appropriately', async () => {
            const falsePositiveContext = createMockContext([{
                path: 'test.js',
                content: '// This is a fake API_KEY=test123 for demonstration\nconst example = "not-a-real-secret";'
            }]);

            const findings = await scanSecrets(falsePositiveContext.repo);

            // Should either find nothing or have low confidence
            const apiKeyFinding = findings.find(f => f.title.includes('API Key'));
            if (apiKeyFinding) {
                expect(apiKeyFinding.confidence).toBeLessThan(0.7);
            }
        });

        it('should redact secrets in descriptions', async () => {
            const findings = await scanSecrets(mockContext.repo);

            findings.forEach(finding => {
                expect(finding.description).not.toContain('password123');
                expect(finding.description).not.toContain('abc123def456');
                expect(finding.description).toContain('[REDACTED]');
            });
        });
    });

    describe('CI Security Reader', () => {
        it('should parse GitHub security alerts', async () => {
            const githubReport: CISecurityReport = {
                source: 'github-security',
                timestamp: new Date().toISOString(),
                findings: [{
                    id: 'gh-1',
                    title: 'React XSS vulnerability',
                    description: 'React XSS vulnerability',
                    severity: SeverityLevel.HIGH,
                    type: VulnerabilityType.DEPENDENCY,
                    component: 'react',
                    cveIds: ['CVE-2021-44906'],
                    confidence: 0.9,
                    source: FindingSource.CI_SECURITY
                }],
                metadata: {}
            };

            const findings = await readCISecurityReports(createMockCI([githubReport]));

            expect(findings).toHaveLength(1);
            expect(findings[0].component).toBe('react');
            expect(findings[0].severity).toBe(SeverityLevel.HIGH);
            expect(findings[0].cveIds).toContain('CVE-2021-44906');
        });

        it('should handle multiple CI report formats', async () => {
            const snykReport: CISecurityReport = {
                source: 'snyk',
                timestamp: new Date().toISOString(),
                findings: [{
                    id: 'snyk-1',
                    title: 'Axios SSRF vulnerability',
                    description: 'Axios SSRF vulnerability',
                    severity: SeverityLevel.MEDIUM,
                    type: VulnerabilityType.DEPENDENCY,
                    component: 'axios',
                    cveIds: ['CVE-2022-1214'],
                    confidence: 0.85,
                    source: FindingSource.CI_SECURITY
                }],
                metadata: {}
            };

            const findings = await readCISecurityReports(createMockCI([snykReport]));

            expect(findings).toHaveLength(1);
            expect(findings[0].component).toBe('axios');
            expect(findings[0].severity).toBe(SeverityLevel.MEDIUM);
        });
    });

    describe('Finding Normalization', () => {
        it('should normalize findings from different sources', () => {
            const rawFindings: SecurityFinding[] = [
                {
                    id: '1',
                    title: 'SQL Injection',
                    description: 'Potential SQL injection vulnerability',
                    severity: 'HIGH' as any, // Simulate string input
                    type: 'INJECTION' as any,
                    component: 'express',
                    filePath: 'server.js',
                    lineNumber: 10,
                    confidence: 0.9,
                    source: FindingSource.SAST_SCANNER
                },
                {
                    id: '2',
                    title: 'Vulnerable Dependency',
                    description: 'Known vulnerability in lodash',
                    severity: 'MEDIUM' as any,
                    type: 'DEPENDENCY' as any,
                    component: 'lodash',
                    cveIds: ['CVE-2019-10744'],
                    confidence: 0.95,
                    source: FindingSource.DEPENDENCY_SCANNER
                }
            ];

            const normalized = normalizeFindings(rawFindings);

            expect(normalized).toHaveLength(2);
            expect(normalized[0].severity).toBe(SeverityLevel.HIGH);
            expect(normalized[0].type).toBe(VulnerabilityType.INJECTION);
            expect(normalized[1].severity).toBe(SeverityLevel.MEDIUM);
            expect(normalized[1].type).toBe(VulnerabilityType.DEPENDENCY);
        });

        it('should handle invalid severity levels', () => {
            const invalidFinding: SecurityFinding = {
                id: '1',
                title: 'Test Vuln',
                description: 'Test',
                severity: 'INVALID' as any,
                type: VulnerabilityType.CODE_VULNERABILITY,
                component: 'test',
                confidence: 0.5,
                source: FindingSource.TEST
            };

            const normalized = normalizeFindings([invalidFinding]);

            expect(normalized[0].severity).toBe(SeverityLevel.MEDIUM); // Default fallback
        });
    });

    describe('Severity Classification', () => {
        it('should adjust severity based on context', () => {
            const findings: SecurityFinding[] = [
                {
                    id: '1',
                    title: 'SQL Injection in Authentication Module',
                    description: 'SQL injection vulnerability that bypasses authentication',
                    severity: SeverityLevel.HIGH,
                    type: VulnerabilityType.INJECTION,
                    component: 'auth',
                    filePath: 'auth/login.js',
                    confidence: 0.9,
                    source: FindingSource.SAST_SCANNER
                }
            ];

            const classified = findings.map(finding => ({
                ...finding,
                severity: classifySeverity(finding)
            }));

            // Should be upgraded to CRITICAL due to auth bypass
            expect(classified[0].severity).toBe(SeverityLevel.CRITICAL);
        });

        it('should consider CVE scores in classification', () => {
            const finding: SecurityFinding = {
                id: '1',
                title: 'Vulnerable Dependency',
                description: 'Known high-severity CVE',
                severity: SeverityLevel.MEDIUM,
                type: VulnerabilityType.DEPENDENCY,
                component: 'express',
                cveIds: ['CVE-2022-24999'],
                confidence: 0.95,
                source: FindingSource.DEPENDENCY_SCANNER
            };

            const classified = [{
                ...finding,
                severity: classifySeverity(finding)
            }];

            // Should be upgraded based on CVE severity
            expect(classified[0].severity).toBe(SeverityLevel.HIGH);
        });
    });

    describe('Deduplication', () => {
        it('should merge duplicate findings from different sources', () => {
            const duplicateFindings: SecurityFinding[] = [
                {
                    id: '1',
                    title: 'Express Vulnerability',
                    description: 'Express.js vulnerability',
                    severity: SeverityLevel.HIGH,
                    type: VulnerabilityType.DEPENDENCY,
                    component: 'express',
                    cveIds: ['CVE-2022-24999'],
                    confidence: 0.9,
                    source: FindingSource.DEPENDENCY_SCANNER
                },
                {
                    id: '2',
                    title: 'Express Security Issue',
                    description: 'Security issue in Express framework',
                    severity: SeverityLevel.HIGH,
                    type: VulnerabilityType.DEPENDENCY,
                    component: 'express',
                    cveIds: ['CVE-2022-24999'],
                    confidence: 0.95,
                    source: FindingSource.CI_SECURITY
                }
            ];

            const deduplicated = deduplicateFindings(duplicateFindings);

            expect(deduplicated).toHaveLength(1);
            expect(deduplicated[0].confidence).toBe(0.95); // Should use higher confidence
            expect(deduplicated[0].source).toContain(FindingSource.DEPENDENCY_SCANNER);
            expect(deduplicated[0].source).toContain(FindingSource.CI_SECURITY);
        });

        it('should not merge unrelated findings', () => {
            const unrelatedFindings: SecurityFinding[] = [
                {
                    id: '1',
                    title: 'SQL Injection',
                    description: 'SQL injection in user query',
                    severity: SeverityLevel.HIGH,
                    type: VulnerabilityType.INJECTION,
                    component: 'express',
                    filePath: 'server.js',
                    lineNumber: 10,
                    confidence: 0.9,
                    source: FindingSource.SAST_SCANNER
                },
                {
                    id: '2',
                    title: 'XSS Vulnerability',
                    description: 'Cross-site scripting in template',
                    severity: SeverityLevel.MEDIUM,
                    type: VulnerabilityType.INJECTION,
                    component: 'express',
                    filePath: 'views/template.html',
                    lineNumber: 5,
                    confidence: 0.8,
                    source: FindingSource.SAST_SCANNER
                }
            ];

            const deduplicated = deduplicateFindings(unrelatedFindings);

            expect(deduplicated).toHaveLength(2); // Should remain separate
        });
    });

    describe('Risk Assessment', () => {
        it('should calculate appropriate risk scores', () => {
            const findings: SecurityFinding[] = [
                {
                    id: '1',
                    title: 'Critical Auth Bypass',
                    description: 'Authentication bypass leading to remote code execution',
                    severity: SeverityLevel.CRITICAL,
                    type: VulnerabilityType.INJECTION,
                    component: 'auth',
                    filePath: 'auth/login.js',
                    confidence: 0.95,
                    source: FindingSource.SAST_SCANNER
                },
                {
                    id: '2',
                    title: 'Info Disclosure',
                    description: 'Debug information exposed',
                    severity: SeverityLevel.LOW,
                    type: VulnerabilityType.CONFIGURATION,
                    component: 'app',
                    filePath: 'config.js',
                    confidence: 0.8,
                    source: FindingSource.CONFIG_SCANNER
                }
            ];

            const riskAssessment = assessRisk(findings);

            expect(riskAssessment.businessCriticality).toBe('CRITICAL');
            expect(riskAssessment.likelihood).toBe('HIGH');
            expect(riskAssessment.riskScore).toBeGreaterThan(0.7);
        });

        it('should handle empty findings gracefully', () => {
            const riskAssessment = assessRisk([]);

            expect(riskAssessment.riskScore).toBe(0.1);
            expect(riskAssessment.businessCriticality).toBe('LOW');
            expect(riskAssessment.likelihood).toBe('LOW');
        });
    });

    describe('Fix Proposals', () => {
        describe('Dependency Fixes', () => {
            it('should generate version upgrade proposals', () => {
                const dependencyFindings: SecurityFinding[] = [
                    {
                        id: '1',
                        title: 'Express Vulnerability CVE-2022-24999',
                        description: 'Express version 4.16.4 has known security vulnerability',
                        severity: SeverityLevel.HIGH,
                        type: VulnerabilityType.DEPENDENCY,
                        component: 'express',
                        cveIds: ['CVE-2022-24999'],
                        confidence: 0.95,
                        source: FindingSource.DEPENDENCY_SCANNER
                    }
                ];

                const proposals = generateDependencyFixes(dependencyFindings);

                expect(proposals).toHaveLength(1);
                expect(proposals[0].type).toBe(RemediationType.DEPENDENCY_UPDATE);
                expect(proposals[0].description).toContain('express');
                expect(proposals[0].description).toContain('4.18.2');
                expect(proposals[0].confidence).toBeGreaterThan(0.9);
            });

            it('should suggest package replacements for deprecated packages', () => {
                const momentFinding: SecurityFinding[] = [
                    {
                        id: '1',
                        title: 'Moment.js Vulnerability',
                        description: 'Moment.js has security issues and is deprecated',
                        severity: SeverityLevel.MEDIUM,
                        type: VulnerabilityType.DEPENDENCY,
                        component: 'moment',
                        cveIds: ['CVE-2022-24785'],
                        confidence: 0.9,
                        source: FindingSource.DEPENDENCY_SCANNER
                    }
                ];

                const proposals = generateDependencyFixes(momentFinding);

                expect(proposals).toHaveLength(1);
                expect(proposals[0].type).toBe(RemediationType.DEPENDENCY_REPLACEMENT);
                expect(proposals[0].description).toContain('dayjs');
                expect(proposals[0].effort).toBe('HIGH');
            });
        });

        describe('Configuration Fixes', () => {
            it('should generate HTTPS enforcement fixes', () => {
                const httpsFindings: SecurityFinding[] = [
                    {
                        id: '1',
                        title: 'Missing HTTPS Enforcement',
                        description: 'Application does not enforce HTTPS connections',
                        severity: SeverityLevel.HIGH,
                        type: VulnerabilityType.CONFIGURATION,
                        component: 'express',
                        filePath: 'server.js',
                        confidence: 0.9,
                        source: FindingSource.CONFIG_SCANNER
                    }
                ];

                const proposals = generateConfigFixes(httpsFindings);

                expect(proposals).toHaveLength(1);
                expect(proposals[0].type).toBe(RemediationType.CONFIGURATION_UPDATE);
                expect(proposals[0].description).toContain('HTTPS');
                expect(proposals[0].changes[0].proposedValue).toContain('helmet');
            });
        });

        describe('Code Fixes', () => {
            it('should generate SQL injection fixes', () => {
                const sqlFindings: SecurityFinding[] = [
                    {
                        id: '1',
                        title: 'SQL Injection Vulnerability',
                        description: 'Unsafe SQL query construction',
                        severity: SeverityLevel.HIGH,
                        type: VulnerabilityType.CODE_VULNERABILITY,
                        component: 'express',
                        filePath: 'server.js',
                        lineNumber: 10,
                        confidence: 0.9,
                        source: FindingSource.SAST_SCANNER
                    }
                ];

                const proposals = generateCodeFixes(sqlFindings);

                expect(proposals).toHaveLength(1);
                expect(proposals[0].type).toBe(RemediationType.CODE_CHANGE);
                expect(proposals[0].description).toContain('SQL injection');
                expect(proposals[0].changes[0].proposedValue).toContain('parameterized');
            });
        });
    });

    describe('Integration Tests', () => {
        it('should run complete security scan workflow', async () => {
            // This would test the complete workflow from scanning to fix generation
            const allFindings: SecurityFinding[] = [];

            // Run all scanners
            allFindings.push(...await scanDependencies(mockContext.repo));
            allFindings.push(...await scanWithSAST(mockContext.repo));
            allFindings.push(...await scanSecrets(mockContext.repo));
            allFindings.push(...await readCISecurityReports(mockContext.ci));

            // Process findings
            const normalized = normalizeFindings(allFindings);
            const classified = normalized.map(finding => ({
                ...finding,
                severity: classifySeverity(finding)
            }));
            const deduplicated = deduplicateFindings(classified);
            const riskAssessment = assessRisk(deduplicated);

            // Generate fixes
            const dependencyFixes = generateDependencyFixes(deduplicated);
            const configFixes = generateConfigFixes(deduplicated);
            const codeFixes = generateCodeFixes(deduplicated);

            const allFixes = [...dependencyFixes, ...configFixes, ...codeFixes];

            // Assertions
            expect(deduplicated.length).toBeGreaterThan(0);
            expect(riskAssessment.riskScore).toBeGreaterThan(0);
            expect(allFixes.length).toBeGreaterThan(0);

            // Verify fix quality
            allFixes.forEach(fix => {
                expect(fix.confidence).toBeGreaterThan(0.5);
                expect(fix.changes.length).toBeGreaterThan(0);
                expect(fix.testing.suggestions.length).toBeGreaterThan(0);
                expect(fix.rollback.procedure).toBeTruthy();
            });
        });

        it('should handle edge cases gracefully', async () => {
            const edgeCaseContext = createMockContext([], {
                enabledScanners: [],
                excludePaths: [],
                scanDependencies: false,
                enableSAST: false,
                scanSecrets: false
            });

            await expect(scanDependencies(edgeCaseContext.repo)).resolves.toEqual([]);
            await expect(scanWithSAST(edgeCaseContext.repo)).resolves.toEqual([]);
            await expect(scanSecrets(edgeCaseContext.repo)).resolves.toEqual([]);
            await expect(readCISecurityReports(edgeCaseContext.ci)).resolves.toEqual([]);
        });
    });
});

/**
 * Test utilities for creating mock data
 */
export const TestUtils = {
    createMockFinding: (overrides: Partial<SecurityFinding> = {}): SecurityFinding => ({
        id: '1',
        title: 'Test Vulnerability',
        description: 'Test vulnerability description',
        severity: SeverityLevel.MEDIUM,
        type: VulnerabilityType.CODE_VULNERABILITY,
        component: 'test',
        confidence: 0.8,
        source: FindingSource.TEST,
        ...overrides
    }),

    createMockContext: (overrides: Partial<ExtensionContext> = {}): ExtensionContext => ({
        ...createMockContext([], {}, []),
        ...overrides
    })
};
