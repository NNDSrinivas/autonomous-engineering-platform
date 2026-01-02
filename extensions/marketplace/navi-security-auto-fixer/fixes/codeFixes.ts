/**
 * Code Vulnerability Fix Proposals
 * 
 * Generates fix proposals for code-level security vulnerabilities including
 * input validation, output encoding, and secure coding practices.
 */

import { SecurityFinding, RemediationProposal, RemediationType, VulnerabilityType } from '../types';

/**
 * Secure code templates for common vulnerabilities
 */
const SECURE_CODE_TEMPLATES = {
    // Input validation templates
    INPUT_VALIDATION: {
        javascript: {
            sqlInjectionFix: `
// Secure: Use parameterized queries
const user = await db.query(
    'SELECT * FROM users WHERE email = $1 AND status = $2',
    [email, 'active']
);`,
            xssPreventionFix: `
// Secure: Sanitize and validate input
const DOMPurify = require('isomorphic-dompurify');
const validator = require('validator');

const sanitizedInput = DOMPurify.sanitize(userInput);
if (!validator.isLength(sanitizedInput, { min: 1, max: 1000 })) {
    throw new Error('Invalid input length');
}`,
            commandInjectionFix: `
// Secure: Use safe alternatives or validate input
const { execSync } = require('child_process');
const path = require('path');

// Validate filename
const filename = path.basename(userInput);
if (!/^[a-zA-Z0-9._-]+$/.test(filename)) {
    throw new Error('Invalid filename');
}

// Use safe path construction
const safePath = path.join('/safe/directory', filename);`
        },
        python: {
            sqlInjectionFix: `
# Secure: Use parameterized queries
cursor.execute(
    "SELECT * FROM users WHERE email = %s AND status = %s",
    (email, 'active')
)`,
            commandInjectionFix: `
# Secure: Use subprocess with proper validation
import subprocess
import shlex
import re

# Validate input
if not re.match(r'^[a-zA-Z0-9._-]+$', filename):
    raise ValueError('Invalid filename')

# Use subprocess safely
result = subprocess.run(
    ['process_file', filename],
    capture_output=True,
    text=True,
    check=True
)`
        },
        java: {
            sqlInjectionFix: `
// Secure: Use PreparedStatement
String sql = "SELECT * FROM users WHERE email = ? AND status = ?";
PreparedStatement stmt = connection.prepareStatement(sql);
stmt.setString(1, email);
stmt.setString(2, "active");
ResultSet rs = stmt.executeQuery();`,
            xssPreventionFix: `
// Secure: Use OWASP Java Encoder
import org.owasp.encoder.Encode;

String safeOutput = Encode.forHtml(userInput);
// For JavaScript context:
String safeJsOutput = Encode.forJavaScript(userInput);`
        }
    },

    // Cryptography templates
    CRYPTOGRAPHY: {
        javascript: {
            secureHashingFix: `
// Secure: Use bcrypt for password hashing
const bcrypt = require('bcrypt');
const saltRounds = 12;

const hashedPassword = await bcrypt.hash(password, saltRounds);`,
            secureRandomFix: `
// Secure: Use crypto.randomBytes for secure random values
const crypto = require('crypto');

const secureToken = crypto.randomBytes(32).toString('hex');`,
            secureEncryptionFix: `
// Secure: Use authenticated encryption
const crypto = require('crypto');

function encrypt(text, key) {
    const iv = crypto.randomBytes(16);
    const cipher = crypto.createCipher('aes-256-gcm', key);
    cipher.setAAD(Buffer.from('additional_data'));
    
    let encrypted = cipher.update(text, 'utf8', 'hex');
    encrypted += cipher.final('hex');
    
    const tag = cipher.getAuthTag();
    
    return {
        iv: iv.toString('hex'),
        encrypted,
        tag: tag.toString('hex')
    };
}`
        }
    },

    // Authentication and authorization
    AUTHENTICATION: {
        javascript: {
            jwtSecurityFix: `
// Secure: JWT with proper validation
const jwt = require('jsonwebtoken');

function generateToken(payload) {
    return jwt.sign(
        payload,
        process.env.JWT_SECRET,
        {
            expiresIn: '15m',
            algorithm: 'HS256',
            issuer: 'your-app-name',
            audience: 'your-app-users'
        }
    );
}

function verifyToken(token) {
    return jwt.verify(token, process.env.JWT_SECRET, {
        algorithms: ['HS256'],
        issuer: 'your-app-name',
        audience: 'your-app-users'
    });
}`,
            sessionSecurityFix: `
// Secure: Session management with regeneration
app.use((req, res, next) => {
    // Regenerate session ID on login
    if (req.session.isAuthenticated && !req.session.regenerated) {
        req.session.regenerated = true;
        req.session.regenerate((err) => {
            if (err) return next(err);
            req.session.isAuthenticated = true;
            next();
        });
    } else {
        next();
    }
});`
        }
    }
};

/**
 * Generate code vulnerability fix proposals
 */
export function generateCodeFixes(findings: SecurityFinding[]): RemediationProposal[] {
    console.log(`🛠️ Generating code fixes for ${findings.length} findings...`);

    const codeFindings = findings.filter(f => f.type === VulnerabilityType.CODE_VULNERABILITY);
    const proposals: RemediationProposal[] = [];

    for (const finding of codeFindings) {
        const fixProposals = createCodeFixProposals(finding);
        proposals.push(...fixProposals);
    }

    console.log(`✅ Generated ${proposals.length} code fix proposals`);
    return proposals;
}

/**
 * Create code fix proposals for a finding
 */
function createCodeFixProposals(finding: SecurityFinding): RemediationProposal[] {
    const vulnerabilityPattern = identifyVulnerabilityPattern(finding);
    const language = detectLanguage(finding.filePath || '');

    switch (vulnerabilityPattern) {
        case 'SQL_INJECTION':
            return [createSQLInjectionFix(finding, language)];
        case 'XSS':
            return [createXSSFix(finding, language)];
        case 'COMMAND_INJECTION':
            return [createCommandInjectionFix(finding, language)];
        case 'WEAK_CRYPTOGRAPHY':
            return [createWeakCryptographyFix(finding, language)];
        case 'INSECURE_RANDOM':
            return [createInsecureRandomFix(finding, language)];
        case 'JWT_SECURITY':
            return [createJWTSecurityFix(finding, language)];
        case 'SESSION_SECURITY':
            return [createSessionSecurityFix(finding, language)];
        case 'PATH_TRAVERSAL':
            return [createPathTraversalFix(finding, language)];
        case 'INSECURE_DESERIALIZATION':
            return [createInsecureDeserializationFix(finding, language)];
        default:
            return [createGenericCodeFix(finding, language)];
    }
}

/**
 * Identify the vulnerability pattern from finding
 */
function identifyVulnerabilityPattern(finding: SecurityFinding): string {
    const text = `${finding.title} ${finding.description}`.toLowerCase();

    if (text.includes('sql injection') || text.includes('sql query')) {
        return 'SQL_INJECTION';
    }

    if (text.includes('xss') || text.includes('cross-site scripting') || text.includes('script injection')) {
        return 'XSS';
    }

    if (text.includes('command injection') || text.includes('code execution')) {
        return 'COMMAND_INJECTION';
    }

    if (text.includes('weak') && (text.includes('crypto') || text.includes('hash') || text.includes('encryption'))) {
        return 'WEAK_CRYPTOGRAPHY';
    }

    if (text.includes('insecure random') || text.includes('weak random')) {
        return 'INSECURE_RANDOM';
    }

    if (text.includes('jwt') || text.includes('json web token')) {
        return 'JWT_SECURITY';
    }

    if (text.includes('session') && text.includes('security')) {
        return 'SESSION_SECURITY';
    }

    if (text.includes('path traversal') || text.includes('directory traversal')) {
        return 'PATH_TRAVERSAL';
    }

    if (text.includes('deserialization') && text.includes('insecure')) {
        return 'INSECURE_DESERIALIZATION';
    }

    return 'UNKNOWN';
}

/**
 * Detect programming language from file path
 */
function detectLanguage(filePath: string): string {
    const ext = filePath.split('.').pop()?.toLowerCase() || '';

    switch (ext) {
        case 'js':
        case 'ts':
        case 'jsx':
        case 'tsx':
            return 'javascript';
        case 'py':
            return 'python';
        case 'java':
            return 'java';
        case 'cs':
            return 'csharp';
        case 'php':
            return 'php';
        case 'rb':
            return 'ruby';
        case 'go':
            return 'go';
        default:
            return 'javascript'; // Default fallback
    }
}

/**
 * Create SQL injection fix
 */
function createSQLInjectionFix(finding: SecurityFinding, language: string): RemediationProposal {
    const template = SECURE_CODE_TEMPLATES.INPUT_VALIDATION[language as keyof typeof SECURE_CODE_TEMPLATES.INPUT_VALIDATION]?.sqlInjectionFix ||
        SECURE_CODE_TEMPLATES.INPUT_VALIDATION.javascript.sqlInjectionFix;

    return {
        type: RemediationType.CODE_CHANGE,
        description: 'Fix SQL injection vulnerability with parameterized queries',
        confidence: 0.9,
        effort: 'MEDIUM',
        risk: 'LOW',
        changes: [{
            filePath: finding.filePath || 'unknown.js',
            changeType: 'CODE_REPLACEMENT',
            currentValue: '// Vulnerable SQL query construction',
            proposedValue: template,
            lineNumber: finding.lineNumber || 1
        }],
        explanation: 'Replace string concatenation in SQL queries with parameterized queries to prevent SQL injection attacks',
        cveIds: finding.cveIds || [],
        testing: {
            required: true,
            suggestions: [
                'Test that legitimate queries still work correctly',
                'Verify that malicious SQL inputs are properly escaped',
                'Test all database operations that use this query',
                'Run automated security tests against injection attacks'
            ]
        },
        rollback: {
            procedure: 'Revert to original query construction method',
            verification: 'Verify database operations work (temporarily accept security risk)'
        }
    };
}

/**
 * Create XSS prevention fix
 */
function createXSSFix(finding: SecurityFinding, language: string): RemediationProposal {
    const templates = SECURE_CODE_TEMPLATES.INPUT_VALIDATION[language as keyof typeof SECURE_CODE_TEMPLATES.INPUT_VALIDATION];
    const template = (templates && 'xssPreventionFix' in templates) 
        ? templates.xssPreventionFix 
        : SECURE_CODE_TEMPLATES.INPUT_VALIDATION.javascript.xssPreventionFix;

    return {
        type: RemediationType.CODE_CHANGE,
        description: 'Add input sanitization and output encoding to prevent XSS',
        confidence: 0.85,
        effort: 'MEDIUM',
        risk: 'LOW',
        changes: [{
            filePath: finding.filePath || 'unknown.js',
            changeType: 'CODE_ADDITION',
            currentValue: '// No input sanitization',
            proposedValue: template,
            lineNumber: finding.lineNumber || 1
        }],
        explanation: 'Add input validation and output encoding to prevent cross-site scripting (XSS) attacks',
        cveIds: finding.cveIds || [],
        testing: {
            required: true,
            suggestions: [
                'Test that legitimate user input is processed correctly',
                'Verify that script tags and other XSS vectors are neutralized',
                'Test HTML rendering to ensure content displays properly',
                'Run XSS scanning tools against the application'
            ]
        },
        rollback: {
            procedure: 'Remove input sanitization code',
            verification: 'Verify user input processing still works (temporarily accept security risk)'
        }
    };
}

/**
 * Create command injection fix
 */
function createCommandInjectionFix(finding: SecurityFinding, language: string): RemediationProposal {
    const templates = SECURE_CODE_TEMPLATES.INPUT_VALIDATION[language as keyof typeof SECURE_CODE_TEMPLATES.INPUT_VALIDATION];
    const template = (templates && 'commandInjectionFix' in templates) 
        ? templates.commandInjectionFix 
        : SECURE_CODE_TEMPLATES.INPUT_VALIDATION.python.commandInjectionFix;

    return {
        type: RemediationType.CODE_CHANGE,
        description: 'Prevent command injection with input validation and safe execution',
        confidence: 0.8,
        effort: 'HIGH',
        risk: 'MEDIUM',
        changes: [{
            filePath: finding.filePath || 'unknown.js',
            changeType: 'CODE_REPLACEMENT',
            currentValue: '// Unsafe command execution',
            proposedValue: template,
            lineNumber: finding.lineNumber || 1
        }],
        explanation: 'Replace unsafe command execution with validated input and safe subprocess calls',
        cveIds: finding.cveIds || [],
        testing: {
            required: true,
            suggestions: [
                'Test that legitimate commands still execute correctly',
                'Verify that malicious command injection attempts are blocked',
                'Test error handling for invalid input',
                'Verify that command output is properly captured and handled'
            ]
        },
        rollback: {
            procedure: 'Revert to original command execution method',
            verification: 'Verify command functionality works (temporarily accept security risk)'
        }
    };
}

/**
 * Create weak cryptography fix
 */
function createWeakCryptographyFix(finding: SecurityFinding, language: string): RemediationProposal {
    const template = SECURE_CODE_TEMPLATES.CRYPTOGRAPHY[language as keyof typeof SECURE_CODE_TEMPLATES.CRYPTOGRAPHY]?.secureHashingFix ||
        SECURE_CODE_TEMPLATES.CRYPTOGRAPHY.javascript.secureHashingFix;

    return {
        type: RemediationType.CODE_CHANGE,
        description: 'Replace weak cryptographic implementation with secure alternative',
        confidence: 0.85,
        effort: 'MEDIUM',
        risk: 'MEDIUM',
        changes: [{
            filePath: finding.filePath || 'unknown.js',
            changeType: 'CODE_REPLACEMENT',
            currentValue: '// Weak cryptographic implementation',
            proposedValue: template,
            lineNumber: finding.lineNumber || 1
        }],
        explanation: 'Replace weak cryptographic algorithms with secure, industry-standard implementations',
        cveIds: finding.cveIds || [],
        testing: {
            required: true,
            suggestions: [
                'Test that existing data can still be validated/decrypted',
                'Verify that new cryptographic operations work correctly',
                'Test performance impact of stronger algorithms',
                'Consider migration strategy for existing encrypted data'
            ]
        },
        rollback: {
            procedure: 'Revert to original cryptographic implementation',
            verification: 'Verify cryptographic operations still work (temporarily accept security risk)'
        }
    };
}

/**
 * Create insecure random fix
 */
function createInsecureRandomFix(finding: SecurityFinding, language: string): RemediationProposal {
    const template = SECURE_CODE_TEMPLATES.CRYPTOGRAPHY[language as keyof typeof SECURE_CODE_TEMPLATES.CRYPTOGRAPHY]?.secureRandomFix ||
        SECURE_CODE_TEMPLATES.CRYPTOGRAPHY.javascript.secureRandomFix;

    return {
        type: RemediationType.CODE_CHANGE,
        description: 'Replace insecure random number generation with cryptographically secure alternative',
        confidence: 0.95,
        effort: 'LOW',
        risk: 'LOW',
        changes: [{
            filePath: finding.filePath || 'unknown.js',
            changeType: 'CODE_REPLACEMENT',
            currentValue: '// Insecure random generation',
            proposedValue: template,
            lineNumber: finding.lineNumber || 1
        }],
        explanation: 'Replace Math.random() or similar insecure random functions with cryptographically secure alternatives',
        cveIds: finding.cveIds || [],
        testing: {
            required: true,
            suggestions: [
                'Test that random values are properly generated',
                'Verify that tokens/IDs are sufficiently random',
                'Test that security-sensitive operations use secure random values',
                'Verify that random values cannot be predicted'
            ]
        },
        rollback: {
            procedure: 'Revert to original random generation method',
            verification: 'Verify random value generation still works (temporarily accept security risk)'
        }
    };
}

/**
 * Create JWT security fix
 */
function createJWTSecurityFix(finding: SecurityFinding, language: string): RemediationProposal {
    const template = SECURE_CODE_TEMPLATES.AUTHENTICATION[language as keyof typeof SECURE_CODE_TEMPLATES.AUTHENTICATION]?.jwtSecurityFix ||
        SECURE_CODE_TEMPLATES.AUTHENTICATION.javascript.jwtSecurityFix;

    return {
        type: RemediationType.CODE_CHANGE,
        description: 'Implement secure JWT handling with proper validation',
        confidence: 0.8,
        effort: 'MEDIUM',
        risk: 'MEDIUM',
        changes: [{
            filePath: finding.filePath || 'unknown.js',
            changeType: 'CODE_REPLACEMENT',
            currentValue: '// Insecure JWT handling',
            proposedValue: template,
            lineNumber: finding.lineNumber || 1
        }],
        explanation: 'Implement proper JWT validation with algorithm specification, expiration, and issuer verification',
        cveIds: finding.cveIds || [],
        testing: {
            required: true,
            suggestions: [
                'Test that legitimate tokens are accepted',
                'Verify that expired tokens are rejected',
                'Test that tampered tokens are rejected',
                'Verify that algorithm confusion attacks are prevented'
            ]
        },
        rollback: {
            procedure: 'Revert to original JWT implementation',
            verification: 'Verify JWT authentication still works (temporarily accept security risk)'
        }
    };
}

/**
 * Create session security fix
 */
function createSessionSecurityFix(finding: SecurityFinding, language: string): RemediationProposal {
    const template = SECURE_CODE_TEMPLATES.AUTHENTICATION[language as keyof typeof SECURE_CODE_TEMPLATES.AUTHENTICATION]?.sessionSecurityFix ||
        SECURE_CODE_TEMPLATES.AUTHENTICATION.javascript.sessionSecurityFix;

    return {
        type: RemediationType.CODE_CHANGE,
        description: 'Implement secure session management',
        confidence: 0.8,
        effort: 'MEDIUM',
        risk: 'MEDIUM',
        changes: [{
            filePath: finding.filePath || 'unknown.js',
            changeType: 'CODE_ADDITION',
            currentValue: '// Insecure session management',
            proposedValue: template,
            lineNumber: finding.lineNumber || 1
        }],
        explanation: 'Implement session ID regeneration and secure session handling to prevent session-based attacks',
        cveIds: finding.cveIds || [],
        testing: {
            required: true,
            suggestions: [
                'Test that session regeneration works correctly',
                'Verify that sessions are properly invalidated on logout',
                'Test that concurrent sessions are handled appropriately',
                'Verify that session fixation attacks are prevented'
            ]
        },
        rollback: {
            procedure: 'Revert to original session handling',
            verification: 'Verify session management still works (temporarily accept security risk)'
        }
    };
}

/**
 * Create path traversal fix
 */
function createPathTraversalFix(finding: SecurityFinding, language: string): RemediationProposal {
    const pathValidationCode = language === 'python' ? `
# Secure: Path validation and sanitization
import os
import os.path

def safe_path_join(base_path, user_path):
    # Normalize and resolve the path
    safe_path = os.path.normpath(os.path.join(base_path, user_path))
    
    # Ensure the path is within the base directory
    if not safe_path.startswith(os.path.abspath(base_path)):
        raise ValueError("Path traversal attempt detected")
    
    return safe_path` : `
// Secure: Path validation and sanitization
const path = require('path');

function safePathJoin(basePath, userPath) {
    // Normalize and resolve the path
    const safePath = path.resolve(basePath, userPath);
    
    // Ensure the path is within the base directory
    if (!safePath.startsWith(path.resolve(basePath))) {
        throw new Error('Path traversal attempt detected');
    }
    
    return safePath;
}`;

    return {
        type: RemediationType.CODE_CHANGE,
        description: 'Add path validation to prevent directory traversal attacks',
        confidence: 0.9,
        effort: 'MEDIUM',
        risk: 'LOW',
        changes: [{
            filePath: finding.filePath || 'unknown.js',
            changeType: 'CODE_REPLACEMENT',
            currentValue: '// Unsafe path construction',
            proposedValue: pathValidationCode,
            lineNumber: finding.lineNumber || 1
        }],
        explanation: 'Add path validation and normalization to prevent directory traversal attacks',
        cveIds: finding.cveIds || [],
        testing: {
            required: true,
            suggestions: [
                'Test that legitimate file paths work correctly',
                'Verify that "../" traversal attempts are blocked',
                'Test that symbolic link traversals are prevented',
                'Verify that file operations are restricted to intended directories'
            ]
        },
        rollback: {
            procedure: 'Revert to original path handling',
            verification: 'Verify file operations still work (temporarily accept security risk)'
        }
    };
}

/**
 * Create insecure deserialization fix
 */
function createInsecureDeserializationFix(finding: SecurityFinding, language: string): RemediationProposal {
    const deserializationCode = language === 'python' ? `
# Secure: Safe deserialization with validation
import json
import pickle
from typing import Dict, Any

def safe_deserialize(data: str, expected_type: type = dict) -> Any:
    try:
        # Use JSON for safe deserialization when possible
        result = json.loads(data)
        
        # Validate the result type
        if not isinstance(result, expected_type):
            raise TypeError(f"Expected {expected_type}, got {type(result)}")
        
        return result
    except (json.JSONDecodeError, TypeError) as e:
        raise ValueError(f"Invalid or unsafe data: {e}")` : `
// Secure: Safe deserialization with validation
function safeDeserialize(data, expectedType = 'object') {
    try {
        // Use JSON.parse for safe deserialization
        const result = JSON.parse(data);
        
        // Validate the result type
        if (typeof result !== expectedType) {
            throw new TypeError(\`Expected \${expectedType}, got \${typeof result}\`);
        }
        
        // Additional validation can be added here
        return result;
    } catch (error) {
        throw new Error(\`Invalid or unsafe data: \${error.message}\`);
    }
}`;

    return {
        type: RemediationType.CODE_CHANGE,
        description: 'Replace insecure deserialization with safe alternatives',
        confidence: 0.8,
        effort: 'HIGH',
        risk: 'HIGH',
        changes: [{
            filePath: finding.filePath || 'unknown.js',
            changeType: 'CODE_REPLACEMENT',
            currentValue: '// Insecure deserialization',
            proposedValue: deserializationCode,
            lineNumber: finding.lineNumber || 1
        }],
        explanation: 'Replace insecure deserialization methods with safe alternatives and input validation',
        cveIds: finding.cveIds || [],
        testing: {
            required: true,
            suggestions: [
                'Test that legitimate serialized data is processed correctly',
                'Verify that malicious payloads are rejected',
                'Test type validation and error handling',
                'Consider migration strategy for existing serialized data'
            ]
        },
        rollback: {
            procedure: 'Revert to original deserialization method',
            verification: 'Verify data processing still works (temporarily accept security risk)'
        }
    };
}

/**
 * Create generic code fix
 */
function createGenericCodeFix(finding: SecurityFinding, _language: string): RemediationProposal {
    return {
        type: RemediationType.CODE_CHANGE,
        description: 'Address security vulnerability in code',
        confidence: 0.5,
        effort: 'MEDIUM',
        risk: 'MEDIUM',
        changes: [{
            filePath: finding.filePath || 'unknown.js',
            changeType: 'CODE_UPDATE',
            currentValue: '// Security vulnerability',
            proposedValue: '// Review and implement secure coding practices',
            lineNumber: finding.lineNumber || 1
        }],
        explanation: `Address security vulnerability: ${finding.description}`,
        cveIds: finding.cveIds || [],
        testing: {
            required: true,
            suggestions: [
                'Review secure coding guidelines for this vulnerability type',
                'Test that the security issue is resolved',
                'Verify that functionality is not broken',
                'Consider adding automated security tests'
            ]
        },
        rollback: {
            procedure: 'Revert code changes',
            verification: 'Verify functionality is restored (temporarily accept security risk)'
        }
    };
}