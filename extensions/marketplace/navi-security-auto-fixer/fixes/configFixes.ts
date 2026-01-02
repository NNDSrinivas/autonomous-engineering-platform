/**
 * Configuration Fix Proposals
 * 
 * Generates fix proposals for security configuration issues including
 * HTTPS enforcement, secure headers, and security policy updates.
 */

import { SecurityFinding, RemediationProposal, RemediationType, VulnerabilityType } from '../types';

/**
 * Security configuration templates and fixes
 */
const SECURITY_CONFIG_FIXES = {
    // Express.js security configurations
    EXPRESS_SECURITY: {
        helmet: `
// Install: npm install helmet
const helmet = require('helmet');
app.use(helmet({
    contentSecurityPolicy: {
        directives: {
            defaultSrc: ["'self'"],
            styleSrc: ["'self'", "'unsafe-inline'"],
            scriptSrc: ["'self'"],
            imgSrc: ["'self'", "data:", "https:"]
        }
    },
    hsts: {
        maxAge: 31536000,
        includeSubDomains: true,
        preload: true
    }
}));`,
        cors: `
const cors = require('cors');
app.use(cors({
    origin: process.env.ALLOWED_ORIGINS?.split(',') || ['http://localhost:3000'],
    credentials: true,
    optionsSuccessStatus: 200
}));`,
        rateLimiting: `
const rateLimit = require("express-rate-limit");
const limiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 100, // limit each IP to 100 requests per windowMs
    message: "Too many requests from this IP, please try again later."
});
app.use(limiter);`
    },

    // HTTPS and TLS configurations
    TLS_CONFIG: {
        nginx: `
server {
    listen 443 ssl http2;
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
    # Modern TLS configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
}`,
        apache: `
<VirtualHost *:443>
    SSLEngine on
    SSLCertificateFile /path/to/certificate.crt
    SSLCertificateKeyFile /path/to/private.key
    
    # Modern TLS configuration
    SSLProtocol -all +TLSv1.2 +TLSv1.3
    SSLCipherSuite ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384
    SSLHonorCipherOrder off
    
    # Security headers
    Header always set Strict-Transport-Security "max-age=63072000; includeSubDomains; preload"
    Header always set X-Frame-Options DENY
    Header always set X-Content-Type-Options nosniff
    Header always set X-XSS-Protection "1; mode=block"
</VirtualHost>`
    },

    // Database security configurations
    DATABASE_SECURITY: {
        mongodb: `
# MongoDB security configuration
security:
    authorization: enabled
    clusterAuthMode: keyFile
    keyFile: /path/to/keyfile
    
net:
    bindIp: 127.0.0.1
    tls:
        mode: requireTLS
        certificateKeyFile: /path/to/mongodb.pem`,
        postgres: `
# PostgreSQL security settings
ssl = on
ssl_cert_file = '/path/to/server.crt'
ssl_key_file = '/path/to/server.key'
ssl_ca_file = '/path/to/ca.crt'

# Connection security
listen_addresses = 'localhost'
max_connections = 100
password_encryption = scram-sha-256`
    }
};

/**
 * Generate configuration fix proposals
 */
export function generateConfigFixes(findings: SecurityFinding[]): RemediationProposal[] {
    console.log(`⚙️ Generating configuration fixes for ${findings.length} findings...`);

    const configFindings = findings.filter(f => f.type === VulnerabilityType.CONFIGURATION);
    const proposals: RemediationProposal[] = [];

    for (const finding of configFindings) {
        const fixProposals = createConfigFixProposals(finding);
        proposals.push(...fixProposals);
    }

    console.log(`✅ Generated ${proposals.length} configuration fix proposals`);
    return proposals;
}

/**
 * Create configuration fix proposals for a finding
 */
function createConfigFixProposals(finding: SecurityFinding): RemediationProposal[] {
    const proposals: RemediationProposal[] = [];

    // Analyze finding to determine configuration type
    const configType = determineConfigurationType(finding);

    switch (configType) {
        case 'HTTPS_MISSING':
            proposals.push(createHttpsEnforcementFix(finding));
            break;
        case 'SECURITY_HEADERS':
            proposals.push(createSecurityHeadersFix(finding));
            break;
        case 'CORS_MISCONFIGURATION':
            proposals.push(createCorsFix(finding));
            break;
        case 'WEAK_TLS':
            proposals.push(createTlsConfigFix(finding));
            break;
        case 'INSECURE_DATABASE':
            proposals.push(createDatabaseSecurityFix(finding));
            break;
        case 'DEBUG_MODE_ENABLED':
            proposals.push(createDebugModeDisableFix(finding));
            break;
        case 'WEAK_SESSION_CONFIG':
            proposals.push(createSessionConfigFix(finding));
            break;
        default:
            proposals.push(createGenericConfigFix(finding));
    }

    return proposals;
}

/**
 * Determine the type of configuration issue
 */
function determineConfigurationType(finding: SecurityFinding): string {
    const text = `${finding.title} ${finding.description}`.toLowerCase();

    if (text.includes('https') || text.includes('ssl') || text.includes('tls')) {
        return 'HTTPS_MISSING';
    }

    if (text.includes('header') || text.includes('csp') || text.includes('x-frame-options')) {
        return 'SECURITY_HEADERS';
    }

    if (text.includes('cors')) {
        return 'CORS_MISCONFIGURATION';
    }

    if (text.includes('debug') && text.includes('enabled')) {
        return 'DEBUG_MODE_ENABLED';
    }

    if (text.includes('session') && (text.includes('weak') || text.includes('insecure'))) {
        return 'WEAK_SESSION_CONFIG';
    }

    if (text.includes('database') || text.includes('mongo') || text.includes('postgres')) {
        return 'INSECURE_DATABASE';
    }

    if (text.includes('tls') && text.includes('weak')) {
        return 'WEAK_TLS';
    }

    return 'GENERIC_CONFIG';
}

/**
 * Create HTTPS enforcement fix
 */
function createHttpsEnforcementFix(finding: SecurityFinding): RemediationProposal {
    const isExpress = finding.filePath?.includes('.js') || finding.component.includes('express');

    return {
        type: RemediationType.CONFIGURATION_UPDATE,
        description: 'Enable HTTPS enforcement and secure transport',
        confidence: 0.9,
        effort: 'MEDIUM',
        risk: 'LOW',
        changes: [{
            filePath: finding.filePath || 'server.js',
            changeType: 'CONFIGURATION_ADDITION',
            currentValue: '// No HTTPS enforcement',
            proposedValue: isExpress ? SECURITY_CONFIG_FIXES.EXPRESS_SECURITY.helmet : 'Enable HTTPS in web server configuration',
            lineNumber: 1
        }],
        explanation: 'Enable HTTPS enforcement to encrypt data in transit and prevent man-in-the-middle attacks',
        cveIds: finding.cveIds || [],
        testing: {
            required: true,
            suggestions: [
                'Test that HTTP requests are redirected to HTTPS',
                'Verify SSL certificate is properly configured',
                'Test that security headers are present in responses',
                'Verify that mixed content warnings are resolved'
            ]
        },
        rollback: {
            procedure: 'Remove HTTPS enforcement configuration and restart server',
            verification: 'Verify application is accessible via HTTP (temporary for rollback only)'
        }
    };
}

/**
 * Create security headers fix
 */
function createSecurityHeadersFix(finding: SecurityFinding): RemediationProposal {
    return {
        type: RemediationType.CONFIGURATION_UPDATE,
        description: 'Add comprehensive security headers',
        confidence: 0.95,
        effort: 'LOW',
        risk: 'LOW',
        changes: [{
            filePath: finding.filePath || 'server.js',
            changeType: 'CONFIGURATION_ADDITION',
            currentValue: '// Missing security headers',
            proposedValue: SECURITY_CONFIG_FIXES.EXPRESS_SECURITY.helmet,
            lineNumber: 1
        }],
        explanation: 'Add security headers including CSP, HSTS, X-Frame-Options to prevent XSS, clickjacking, and other attacks',
        cveIds: finding.cveIds || [],
        testing: {
            required: true,
            suggestions: [
                'Use browser dev tools to verify security headers are present',
                'Test that CSP policy allows legitimate resources',
                'Verify that X-Frame-Options prevents iframe embedding',
                'Check that HSTS header enforces HTTPS'
            ]
        },
        rollback: {
            procedure: 'Remove helmet middleware or security header configuration',
            verification: 'Verify headers are no longer present in HTTP responses'
        }
    };
}

/**
 * Create CORS configuration fix
 */
function createCorsFix(finding: SecurityFinding): RemediationProposal {
    return {
        type: RemediationType.CONFIGURATION_UPDATE,
        description: 'Configure secure CORS policy',
        confidence: 0.85,
        effort: 'LOW',
        risk: 'MEDIUM',
        changes: [{
            filePath: finding.filePath || 'server.js',
            changeType: 'CONFIGURATION_UPDATE',
            currentValue: 'app.use(cors())', // Permissive CORS
            proposedValue: SECURITY_CONFIG_FIXES.EXPRESS_SECURITY.cors,
            lineNumber: 0
        }],
        explanation: 'Configure CORS to only allow trusted origins and prevent unauthorized cross-origin requests',
        cveIds: finding.cveIds || [],
        testing: {
            required: true,
            suggestions: [
                'Test that legitimate frontend origins can access the API',
                'Verify that unauthorized origins are blocked',
                'Test preflight requests work correctly',
                'Ensure credentials are handled securely'
            ]
        },
        rollback: {
            procedure: 'Revert to previous CORS configuration',
            verification: 'Verify legitimate cross-origin requests still work'
        }
    };
}

/**
 * Create TLS configuration fix
 */
function createTlsConfigFix(finding: SecurityFinding): RemediationProposal {
    const configType = finding.filePath?.includes('nginx') ? 'nginx' : 'apache';

    return {
        type: RemediationType.CONFIGURATION_UPDATE,
        description: 'Update TLS configuration to use secure protocols and ciphers',
        confidence: 0.8,
        effort: 'MEDIUM',
        risk: 'MEDIUM',
        changes: [{
            filePath: finding.filePath || `${configType}.conf`,
            changeType: 'CONFIGURATION_UPDATE',
            currentValue: '// Weak TLS configuration',
            proposedValue: SECURITY_CONFIG_FIXES.TLS_CONFIG[configType as keyof typeof SECURITY_CONFIG_FIXES.TLS_CONFIG],
            lineNumber: 0
        }],
        explanation: 'Update TLS configuration to use only secure protocols (TLS 1.2+) and strong cipher suites',
        cveIds: finding.cveIds || [],
        testing: {
            required: true,
            suggestions: [
                'Use SSL Labs test to verify TLS configuration',
                'Test that weak protocols (TLS 1.0, 1.1) are disabled',
                'Verify that strong cipher suites are preferred',
                'Test that certificate chain is properly configured'
            ]
        },
        rollback: {
            procedure: 'Revert to previous TLS configuration',
            verification: 'Verify SSL/TLS connections still work with compatible clients'
        }
    };
}

/**
 * Create database security fix
 */
function createDatabaseSecurityFix(finding: SecurityFinding): RemediationProposal {
    const dbType = finding.component.toLowerCase().includes('mongo') ? 'mongodb' : 'postgres';

    return {
        type: RemediationType.CONFIGURATION_UPDATE,
        description: `Secure ${dbType} configuration`,
        confidence: 0.8,
        effort: 'HIGH',
        risk: 'HIGH',
        changes: [{
            filePath: finding.filePath || `${dbType}.conf`,
            changeType: 'CONFIGURATION_UPDATE',
            currentValue: '// Insecure database configuration',
            proposedValue: SECURITY_CONFIG_FIXES.DATABASE_SECURITY[dbType as keyof typeof SECURITY_CONFIG_FIXES.DATABASE_SECURITY],
            lineNumber: 0
        }],
        explanation: `Enable authentication, encryption, and secure network binding for ${dbType}`,
        cveIds: finding.cveIds || [],
        testing: {
            required: true,
            suggestions: [
                'Test that authentication is required for database access',
                'Verify that network access is restricted to authorized hosts',
                'Test that encrypted connections work properly',
                'Ensure existing application connections still work'
            ]
        },
        rollback: {
            procedure: 'Revert database configuration and restart database service',
            verification: 'Verify database connectivity and application functionality'
        }
    };
}

/**
 * Create debug mode disable fix
 */
function createDebugModeDisableFix(finding: SecurityFinding): RemediationProposal {
    return {
        type: RemediationType.CONFIGURATION_UPDATE,
        description: 'Disable debug mode in production',
        confidence: 0.95,
        effort: 'LOW',
        risk: 'LOW',
        changes: [{
            filePath: finding.filePath || '.env',
            changeType: 'CONFIGURATION_UPDATE',
            currentValue: 'DEBUG=true',
            proposedValue: 'DEBUG=false',
            lineNumber: 0
        }],
        explanation: 'Disable debug mode to prevent information disclosure and improve security',
        cveIds: finding.cveIds || [],
        testing: {
            required: true,
            suggestions: [
                'Verify that debug information is not exposed in error responses',
                'Test that application logging still works appropriately',
                'Ensure error handling provides user-friendly messages',
                'Verify that stack traces are not exposed to end users'
            ]
        },
        rollback: {
            procedure: 'Re-enable debug mode by setting DEBUG=true',
            verification: 'Verify debug information is available for troubleshooting'
        }
    };
}

/**
 * Create session configuration fix
 */
function createSessionConfigFix(finding: SecurityFinding): RemediationProposal {
    const sessionConfig = `
app.use(session({
    secret: process.env.SESSION_SECRET, // Use environment variable
    resave: false,
    saveUninitialized: false,
    cookie: {
        secure: true, // Require HTTPS
        httpOnly: true, // Prevent XSS
        maxAge: 24 * 60 * 60 * 1000, // 24 hours
        sameSite: 'strict' // CSRF protection
    },
    store: new MongoStore({ // Use persistent store
        mongoUrl: process.env.MONGODB_URI
    })
}));`;

    return {
        type: RemediationType.CONFIGURATION_UPDATE,
        description: 'Configure secure session management',
        confidence: 0.9,
        effort: 'MEDIUM',
        risk: 'MEDIUM',
        changes: [{
            filePath: finding.filePath || 'server.js',
            changeType: 'CONFIGURATION_UPDATE',
            currentValue: '// Insecure session configuration',
            proposedValue: sessionConfig,
            lineNumber: 0
        }],
        explanation: 'Configure sessions with secure cookies, proper expiration, and persistent storage',
        cveIds: finding.cveIds || [],
        testing: {
            required: true,
            suggestions: [
                'Test that sessions work correctly with secure cookie settings',
                'Verify that session data persists across server restarts',
                'Test session expiration functionality',
                'Ensure CSRF protection is effective'
            ]
        },
        rollback: {
            procedure: 'Revert to previous session configuration',
            verification: 'Verify user authentication and session management still work'
        }
    };
}

/**
 * Create generic configuration fix
 */
function createGenericConfigFix(finding: SecurityFinding): RemediationProposal {
    return {
        type: RemediationType.CONFIGURATION_UPDATE,
        description: 'Update security configuration',
        confidence: 0.6,
        effort: 'MEDIUM',
        risk: 'MEDIUM',
        changes: [{
            filePath: finding.filePath || 'config.js',
            changeType: 'CONFIGURATION_UPDATE',
            currentValue: '// Insecure configuration',
            proposedValue: '// Review and update configuration for security best practices',
            lineNumber: 0
        }],
        explanation: `Address configuration security issue: ${finding.description}`,
        cveIds: finding.cveIds || [],
        testing: {
            required: true,
            suggestions: [
                'Review security best practices for this configuration',
                'Test that the change doesn\'t break existing functionality',
                'Verify that the security issue is resolved',
                'Consult documentation for secure configuration options'
            ]
        },
        rollback: {
            procedure: 'Revert configuration changes',
            verification: 'Verify application functionality is restored'
        }
    };
}