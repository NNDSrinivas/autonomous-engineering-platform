/**
 * Bundle Verification Script
 * 
 * Verifies the integrity and signature of .navi-ext bundle files
 * to ensure they haven't been tampered with.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const BUNDLE_DIR = path.resolve(__dirname, '..', 'bundle');

console.log('🔍 Verifying NAVI Kubernetes Diagnostics Extension Bundle...');

// Find bundle files
const bundleFiles = fs.readdirSync(BUNDLE_DIR)
    .filter(file => file.endsWith('.navi-ext'))
    .sort((a, b) => b.localeCompare(a)); // Latest first

if (bundleFiles.length === 0) {
    console.error('❌ No bundle files found. Run "npm run create-bundle" first.');
    process.exit(1);
}

const bundlePath = path.join(BUNDLE_DIR, bundleFiles[0]);
console.log(`📦 Verifying bundle: ${bundleFiles[0]}`);

// Load and parse bundle
let bundle;
try {
    const bundleContent = fs.readFileSync(bundlePath, 'utf8');
    bundle = JSON.parse(bundleContent);
} catch (error) {
    console.error('❌ Failed to parse bundle file:', error.message);
    process.exit(1);
}

console.log('\n🏗️ Bundle Structure Verification...');

// Verify bundle structure
const requiredFields = ['manifest', 'package', 'files', 'checksums', 'signature', 'createdAt', 'bundleVersion'];
const missingFields = requiredFields.filter(field => !(field in bundle));

if (missingFields.length > 0) {
    console.error(`❌ Missing required fields: ${missingFields.join(', ')}`);
    process.exit(1);
}

console.log('✅ Bundle structure is valid');

// Verify manifest
console.log('\n📋 Manifest Verification...');
const manifest = bundle.manifest;

if (!manifest.id || !manifest.version || !manifest.trustLevel || !manifest.permissions) {
    console.error('❌ Invalid manifest structure');
    process.exit(1);
}

if (manifest.trustLevel !== 'CORE') {
    console.error('❌ Invalid trust level for Kubernetes diagnostics extension');
    process.exit(1);
}

const requiredPermissions = ['K8S_READ', 'K8S_LOGS', 'REQUEST_APPROVAL', 'PROPOSE_ACTIONS'];
const missingPermissions = requiredPermissions.filter(perm => !manifest.permissions.includes(perm));

if (missingPermissions.length > 0) {
    console.error(`❌ Missing required permissions: ${missingPermissions.join(', ')}`);
    process.exit(1);
}

console.log('✅ Manifest is valid');
console.log(`   ID: ${manifest.id}`);
console.log(`   Version: ${manifest.version}`);
console.log(`   Trust Level: ${manifest.trustLevel}`);
console.log(`   Permissions: ${manifest.permissions.length}`);

// Verify file checksums
console.log('\n🔒 File Integrity Verification...');
let checksumFailures = 0;

for (const [filePath, content] of Object.entries(bundle.files)) {
    const expectedChecksum = bundle.checksums[filePath];
    if (!expectedChecksum) {
        console.error(`❌ Missing checksum for file: ${filePath}`);
        checksumFailures++;
        continue;
    }

    const actualChecksum = crypto.createHash('sha256').update(content).digest('hex');
    if (actualChecksum !== expectedChecksum) {
        console.error(`❌ Checksum mismatch for ${filePath}`);
        console.error(`   Expected: ${expectedChecksum}`);
        console.error(`   Actual: ${actualChecksum}`);
        checksumFailures++;
    } else {
        console.log(`✅ ${filePath} (${content.length} bytes)`);
    }
}

if (checksumFailures > 0) {
    console.error(`❌ ${checksumFailures} file(s) failed checksum verification`);
    process.exit(1);
}

console.log('✅ All file checksums verified');

// Verify signature
console.log('\n🔐 Signature Verification...');
const signature = bundle.signature;

if (!signature || !signature.signature || !signature.bundleHash || !signature.algorithm) {
    console.error('❌ Invalid signature structure');
    process.exit(1);
}

// Recreate bundle content without signature for verification
const bundleForVerification = JSON.stringify({
    ...bundle,
    signature: null
}, null, 2);

const actualBundleHash = crypto.createHash('sha256').update(bundleForVerification).digest('hex');

if (actualBundleHash !== signature.bundleHash) {
    console.error('❌ Bundle hash mismatch');
    console.error(`   Expected: ${signature.bundleHash}`);
    console.error(`   Actual: ${actualBundleHash}`);
    process.exit(1);
}

// Verify HMAC signature (in production, this would use public key verification)
const expectedSignature = crypto
    .createHmac('sha256', 'navi-extension-signing-key-dev')
    .update(signature.bundleHash)
    .digest('hex');

if (expectedSignature !== signature.signature) {
    console.error('❌ Signature verification failed');
    process.exit(1);
}

console.log('✅ Signature verification passed');
console.log(`   Algorithm: ${signature.algorithm}`);
console.log(`   Signed by: ${signature.signedBy}`);
console.log(`   Signed at: ${signature.signedAt}`);
console.log(`   Bundle hash: ${signature.bundleHash.substring(0, 16)}...`);

// Verify required files are present
console.log('\n📁 Required Files Verification...');
const requiredFiles = ['dist/index.js', 'dist/types.d.ts', 'manifest.json'];
const missingFiles = requiredFiles.filter(file => !(file in bundle.files));

if (missingFiles.length > 0) {
    console.error(`❌ Missing required files: ${missingFiles.join(', ')}`);
    process.exit(1);
}

console.log('✅ All required files present');

// Verify TypeScript compilation
console.log('\n⚙️ Extension Code Verification...');
const indexJs = bundle.files['dist/index.js'];
const typesDs = bundle.files['dist/types.d.ts'];

if (!indexJs.includes('onInvoke')) {
    console.error('❌ Main entry point function not found in index.js');
    process.exit(1);
}

if (!indexJs.includes('Kubernetes Diagnostics Extension')) {
    console.error('❌ Extension identifier not found in compiled code');
    process.exit(1);
}

if (!typesDs.includes('ExtensionContext') || !typesDs.includes('DiagnosticsResult')) {
    console.error('❌ Required TypeScript types not found');
    process.exit(1);
}

console.log('✅ Extension code verification passed');

// Bundle statistics
console.log('\n📊 Bundle Statistics:');
const bundleSize = fs.statSync(bundlePath).size;
console.log(`   Bundle size: ${(bundleSize / 1024).toFixed(2)} KB`);
console.log(`   Files included: ${Object.keys(bundle.files).length}`);
console.log(`   Total code size: ${Object.values(bundle.files).reduce((sum, content) => sum + content.length, 0)} bytes`);
console.log(`   Created: ${bundle.createdAt}`);
console.log(`   Bundle version: ${bundle.bundleVersion}`);

// Security checks
console.log('\n🛡️ Security Verification...');
const indexContent = bundle.files['dist/index.js'];

// Check for dangerous patterns
const dangerousPatterns = [
    { pattern: /eval\(/, description: 'eval() usage' },
    { pattern: /Function\(/, description: 'Function constructor' },
    { pattern: /process\.exit\(/, description: 'process.exit() calls' },
    { pattern: /require\(['"]child_process['"]/, description: 'child_process import' },
    { pattern: /spawn|exec|fork/, description: 'process spawning' }
];

let securityIssues = 0;
for (const { pattern, description } of dangerousPatterns) {
    if (pattern.test(indexContent)) {
        console.warn(`⚠️ Potential security issue: ${description}`);
        securityIssues++;
    }
}

if (securityIssues === 0) {
    console.log('✅ No security issues detected');
} else {
    console.log(`⚠️ ${securityIssues} potential security issue(s) found - review recommended`);
}

console.log('\n🎉 Bundle verification completed successfully!');
console.log('\n📋 Bundle Summary:');
console.log(`   Extension: ${manifest.id} v${manifest.version}`);
console.log(`   Trust Level: ${manifest.trustLevel}`);
console.log(`   Permissions: ${manifest.permissions.length} granted`);
console.log(`   Bundle: ${bundleFiles[0]}`);
console.log(`   Size: ${(bundleSize / 1024).toFixed(2)} KB`);
console.log(`   Integrity: ✅ Verified`);
console.log(`   Signature: ✅ Valid`);

console.log('\n✅ Bundle is ready for production deployment!');

// Create verification report
const reportPath = path.join(BUNDLE_DIR, `${manifest.id}-v${manifest.version}.verification.json`);
const verificationReport = {
    extensionId: manifest.id,
    version: manifest.version,
    bundlePath: bundlePath,
    verifiedAt: new Date().toISOString(),
    verificationResults: {
        structure: 'PASS',
        manifest: 'PASS',
        fileIntegrity: 'PASS',
        signature: 'PASS',
        requiredFiles: 'PASS',
        codeVerification: 'PASS',
        security: securityIssues === 0 ? 'PASS' : 'WARN'
    },
    bundleStats: {
        size: bundleSize,
        fileCount: Object.keys(bundle.files).length,
        codeSize: Object.values(bundle.files).reduce((sum, content) => sum + content.length, 0)
    },
    securityIssues: securityIssues,
    overallStatus: securityIssues === 0 ? 'VERIFIED' : 'VERIFIED_WITH_WARNINGS'
};

fs.writeFileSync(reportPath, JSON.stringify(verificationReport, null, 2));
console.log(`📄 Verification report saved: ${path.basename(reportPath)}`);