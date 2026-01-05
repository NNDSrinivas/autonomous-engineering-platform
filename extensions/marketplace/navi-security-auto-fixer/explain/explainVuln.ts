/**
 * Vulnerability Explanation Module
 * 
 * Provides human-readable explanations of security vulnerabilities
 */

import { SecurityFinding, VulnerabilityType } from '../types';

export interface VulnerabilityExplanation {
    summary: string;
    technicalDetails: string;
    businessImpact: string;
    attackScenarios: string[];
    recommendations: string[];
}

/**
 * Generate human-readable explanation for a vulnerability
 */
export function explainVulnerability(finding: SecurityFinding): VulnerabilityExplanation {
    console.log(`📖 Generating explanation for ${finding.type} vulnerability: ${finding.title}`);
    
    switch (finding.type) {
        case VulnerabilityType.DEPENDENCY:
            return explainDependencyVulnerability(finding);
        case VulnerabilityType.INJECTION:
            return explainInjectionVulnerability(finding);
        case VulnerabilityType.SECRET_EXPOSURE:
            return explainSecretExposureVulnerability(finding);
        case VulnerabilityType.WEAK_CRYPTO:
            return explainWeakCryptographyVulnerability(finding);
        case VulnerabilityType.CONFIGURATION:
            return explainConfigurationVulnerability(finding);
        case VulnerabilityType.INSECURE_DESERIALIZATION:
            return explainDeserializationVulnerability(finding);
        default:
            return explainGenericVulnerability(finding);
    }
}

function explainDependencyVulnerability(finding: SecurityFinding): VulnerabilityExplanation {
    const cveList = (finding.cveIds && finding.cveIds.length > 0)
        ? finding.cveIds.join(', ')
        : 'none listed';

    return {
        summary: `The ${finding.component} dependency has known security vulnerabilities that could be exploited by attackers.`,
        technicalDetails: `This application uses ${finding.component}, which contains security flaws tracked by CVE identifiers: ${cveList}. These vulnerabilities may allow unauthorized access, data manipulation, or service disruption.`,
        businessImpact: 'Using vulnerable dependencies can expose your application to attacks, potentially leading to data breaches, service outages, and compliance violations.',
        attackScenarios: [
            'Attackers could exploit known vulnerabilities to gain unauthorized access',
            'Malicious payloads could be injected through vulnerable dependency functions',
            'Denial of service attacks could be launched against vulnerable components'
        ],
        recommendations: [
            `Update ${finding.component} to the latest secure version`,
            'Implement automated dependency scanning in your CI/CD pipeline',
            'Monitor security advisories for your dependencies regularly',
            'Consider using alternative packages with better security track records'
        ]
    };
}

function explainInjectionVulnerability(finding: SecurityFinding): VulnerabilityExplanation {
    const injectionType = finding.title.toLowerCase().includes('sql') ? 'SQL injection' :
                         finding.title.toLowerCase().includes('command') ? 'command injection' :
                         'injection';
    
    return {
        summary: `The application contains a ${injectionType} vulnerability where user input is not properly sanitized.`,
        technicalDetails: `User-controlled input is being directly incorporated into ${injectionType === 'SQL injection' ? 'SQL queries' : injectionType === 'command injection' ? 'system commands' : 'executable code'} without proper validation or escaping, allowing attackers to inject malicious code.`,
        businessImpact: `${injectionType} vulnerabilities can lead to complete system compromise, including unauthorized data access, data manipulation, and potential takeover of the entire application.`,
        attackScenarios: [
            injectionType === 'SQL injection' ? 'Attackers could extract sensitive data from your database' : 'Attackers could execute arbitrary system commands',
            injectionType === 'SQL injection' ? 'Database contents could be modified or deleted' : 'System files could be accessed or modified',
            'Authentication could be bypassed entirely',
            'The vulnerability could be used as a stepping stone for further attacks'
        ],
        recommendations: [
            injectionType === 'SQL injection' ? 'Use parameterized queries or prepared statements' : 'Validate and sanitize all user input',
            'Implement input validation with allow-lists rather than deny-lists',
            'Apply the principle of least privilege to database/system accounts',
            'Consider using stored procedures or ORM frameworks with built-in protections'
        ]
    };
}

function explainSecretExposureVulnerability(_finding: SecurityFinding): VulnerabilityExplanation {
    return {
        summary: 'Sensitive credentials or API keys are exposed in your code, making them accessible to unauthorized parties.',
        technicalDetails: `Hardcoded secrets such as API keys, database passwords, or cryptographic keys are stored directly in source code files, configuration files, or version control systems where they can be easily discovered.`,
        businessImpact: 'Exposed secrets can lead to unauthorized access to external services, data breaches, financial losses from API abuse, and compliance violations.',
        attackScenarios: [
            'Exposed API keys could be used to access third-party services at your expense',
            'Database credentials could allow direct access to sensitive data',
            'Cryptographic keys could be used to decrypt confidential information',
            'Secrets could be harvested from public repositories or compromised systems'
        ],
        recommendations: [
            'Move all secrets to environment variables or secure secret management systems',
            'Implement secret rotation policies and procedures',
            'Use service accounts and IAM roles instead of hardcoded credentials',
            'Scan repositories regularly for accidentally committed secrets',
            'Revoke and replace any exposed credentials immediately'
        ]
    };
}

function explainWeakCryptographyVulnerability(_finding: SecurityFinding): VulnerabilityExplanation {
    return {
        summary: 'The application uses weak or outdated cryptographic algorithms that can be easily broken by modern attacks.',
        technicalDetails: 'Weak cryptographic implementations such as MD5, SHA1, or deprecated encryption algorithms provide insufficient security against current computational capabilities and attack techniques.',
        businessImpact: 'Weak cryptography can lead to data confidentiality breaches, integrity violations, and regulatory compliance failures.',
        attackScenarios: [
            'Password hashes could be cracked using rainbow tables or brute force attacks',
            'Encrypted data could be decrypted by attackers with sufficient resources',
            'Digital signatures could be forged or manipulated',
            'Session tokens could be predicted or duplicated'
        ],
        recommendations: [
            'Replace weak algorithms with modern, secure alternatives (e.g., bcrypt for passwords, AES-256 for encryption)',
            'Use cryptographically secure random number generators',
            'Implement proper key management practices',
            'Regularly review and update cryptographic implementations'
        ]
    };
}

function explainConfigurationVulnerability(_finding: SecurityFinding): VulnerabilityExplanation {
    return {
        summary: 'Security-relevant configuration settings are not properly configured, creating potential attack vectors.',
        technicalDetails: 'The application or its supporting infrastructure has insecure configuration settings such as debug mode enabled in production, weak SSL/TLS settings, or overly permissive access controls.',
        businessImpact: 'Configuration vulnerabilities can expose sensitive information, allow unauthorized access, and create opportunities for various attack vectors.',
        attackScenarios: [
            'Debug information could reveal sensitive application details to attackers',
            'Weak SSL/TLS configurations could allow man-in-the-middle attacks',
            'Permissive CORS settings could enable cross-site request forgery',
            'Default credentials or settings could provide easy access points'
        ],
        recommendations: [
            'Follow security configuration best practices and hardening guides',
            'Disable debug mode and verbose error messages in production',
            'Implement strong SSL/TLS configurations with current protocols',
            'Regularly audit and review security configurations',
            'Use configuration management tools to enforce consistent settings'
        ]
    };
}

function explainDeserializationVulnerability(_finding: SecurityFinding): VulnerabilityExplanation {
    return {
        summary: 'The application deserializes untrusted data without proper validation, potentially allowing arbitrary code execution.',
        technicalDetails: 'Insecure deserialization occurs when untrusted data is used to reconstruct objects in memory, potentially allowing attackers to manipulate the deserialization process to execute arbitrary code or perform other malicious actions.',
        businessImpact: 'Insecure deserialization can lead to remote code execution, privilege escalation, and complete system compromise.',
        attackScenarios: [
            'Malicious serialized objects could execute arbitrary code during deserialization',
            'Application logic could be bypassed through object manipulation',
            'Denial of service attacks could be launched through resource exhaustion',
            'Authentication and authorization controls could be circumvented'
        ],
        recommendations: [
            'Avoid deserializing data from untrusted sources when possible',
            'Implement strict input validation and type checking',
            'Use safe serialization formats like JSON instead of binary formats',
            'Apply the principle of least privilege to deserialization operations',
            'Consider using allow-lists for acceptable classes during deserialization'
        ]
    };
}

function explainGenericVulnerability(finding: SecurityFinding): VulnerabilityExplanation {
    return {
        summary: `A ${finding.type.toLowerCase().replace('_', ' ')} vulnerability has been detected in your application.`,
        technicalDetails: finding.description,
        businessImpact: 'This vulnerability could potentially impact the security, availability, or integrity of your application and data.',
        attackScenarios: [
            'Attackers could exploit this vulnerability to compromise your application',
            'Unauthorized access to sensitive data or functionality could occur',
            'The vulnerability could be chained with other attacks for greater impact'
        ],
        recommendations: [
            'Review the specific vulnerability details and implement appropriate fixes',
            'Follow security best practices for this type of vulnerability',
            'Consider implementing additional security controls as defense-in-depth measures',
            'Regularly scan and test your application for security vulnerabilities'
        ]
    };
}
