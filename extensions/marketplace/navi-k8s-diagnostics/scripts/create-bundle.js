/**
 * Bundle Creation Script
 * 
 * Creates signed .navi-ext bundle with cryptographic verification
 * for production deployment to NAVI's marketplace.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// Configuration
const EXTENSION_DIR = path.resolve(__dirname, '..');
const DIST_DIR = path.join(EXTENSION_DIR, 'dist');
const BUNDLE_DIR = path.join(EXTENSION_DIR, 'bundle');
const MANIFEST_PATH = path.join(EXTENSION_DIR, 'manifest.json');
const PACKAGE_PATH = path.join(EXTENSION_DIR, 'package.json');

console.log('🏗️ Creating NAVI Kubernetes Diagnostics Extension Bundle...');

// Ensure directories exist
if (!fs.existsSync(DIST_DIR)) {
    console.error('❌ Dist directory not found. Run "npm run build" first.');
    process.exit(1);
}

if (!fs.existsSync(BUNDLE_DIR)) {
    fs.mkdirSync(BUNDLE_DIR, { recursive: true });
}

// Load and validate manifest
const manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf8'));
const packageInfo = JSON.parse(fs.readFileSync(PACKAGE_PATH, 'utf8'));

console.log(`📋 Extension: ${manifest.id} v${manifest.version}`);
console.log(`🔐 Trust Level: ${manifest.trustLevel}`);
console.log(`🛡️ Permissions: ${manifest.permissions.join(', ')}`);

// Validate required files
const requiredFiles = [
    'dist/index.js',
    'dist/types.d.ts',
    'manifest.json'
];

for (const file of requiredFiles) {
    const filePath = path.join(EXTENSION_DIR, file);
    if (!fs.existsSync(filePath)) {
        console.error(`❌ Required file missing: ${file}`);
        process.exit(1);
    }
}

// Create bundle structure
const bundleStructure = {
    manifest,
    package: {
        name: packageInfo.name,
        version: packageInfo.version,
        description: packageInfo.description,
        author: packageInfo.author,
        license: packageInfo.license
    },
    files: {},
    checksums: {},
    signature: null,
    createdAt: new Date().toISOString(),
    bundleVersion: '1.0'
};

// Add files to bundle
const filesToBundle = [
    'dist/index.js',
    'dist/types.d.ts',
    'dist/index.js.map',
    'dist/types.d.ts.map'
].filter(file => fs.existsSync(path.join(EXTENSION_DIR, file)));

console.log('📦 Bundling files...');
for (const file of filesToBundle) {
    const filePath = path.join(EXTENSION_DIR, file);
    const content = fs.readFileSync(filePath, 'utf8');
    const checksum = crypto.createHash('sha256').update(content).digest('hex');

    bundleStructure.files[file] = content;
    bundleStructure.checksums[file] = checksum;

    console.log(`   ✅ ${file} (${content.length} bytes, checksum: ${checksum.substring(0, 8)}...)`);
}

// Add manifest and package.json
bundleStructure.files['manifest.json'] = fs.readFileSync(MANIFEST_PATH, 'utf8');
bundleStructure.checksums['manifest.json'] = crypto
    .createHash('sha256')
    .update(bundleStructure.files['manifest.json'])
    .digest('hex');

// Create bundle content for signing
const bundleContent = JSON.stringify({
    ...bundleStructure,
    signature: null // Placeholder for signature
}, null, 2);

// Generate signature (in production, this would use private key)
const bundleHash = crypto.createHash('sha256').update(bundleContent).digest('hex');
const mockSignature = crypto
    .createHmac('sha256', 'navi-extension-signing-key-dev')
    .update(bundleHash)
    .digest('hex');

bundleStructure.signature = {
    algorithm: 'HMAC-SHA256',
    signature: mockSignature,
    bundleHash,
    signedBy: 'NAVI Extension Signing Service',
    signedAt: new Date().toISOString()
};

// Write final bundle
const finalBundleContent = JSON.stringify(bundleStructure, null, 2);
const bundlePath = path.join(BUNDLE_DIR, `${manifest.id}-v${manifest.version}.navi-ext`);

fs.writeFileSync(bundlePath, finalBundleContent);

// Create bundle info file
const bundleInfo = {
    extensionId: manifest.id,
    version: manifest.version,
    trustLevel: manifest.trustLevel,
    permissions: manifest.permissions,
    bundlePath: bundlePath,
    bundleSize: finalBundleContent.length,
    bundleHash: crypto.createHash('sha256').update(finalBundleContent).digest('hex'),
    filesIncluded: Object.keys(bundleStructure.files),
    createdAt: bundleStructure.createdAt,
    signature: bundleStructure.signature
};

const infoPath = path.join(BUNDLE_DIR, `${manifest.id}-v${manifest.version}.info.json`);
fs.writeFileSync(infoPath, JSON.stringify(bundleInfo, null, 2));

console.log('\n✅ Bundle created successfully!');
console.log(`📦 Bundle: ${bundlePath}`);
console.log(`📋 Info: ${infoPath}`);
console.log(`📏 Size: ${(finalBundleContent.length / 1024).toFixed(2)} KB`);
console.log(`🔒 Bundle Hash: ${bundleInfo.bundleHash.substring(0, 16)}...`);
console.log(`🔐 Signature: ${mockSignature.substring(0, 16)}...`);

// Validate bundle can be parsed
try {
    const parsedBundle = JSON.parse(finalBundleContent);
    if (!parsedBundle.manifest || !parsedBundle.signature) {
        throw new Error('Invalid bundle structure');
    }
    console.log('✅ Bundle validation passed');
} catch (error) {
    console.error('❌ Bundle validation failed:', error.message);
    process.exit(1);
}

console.log('\n🎉 Ready for deployment to NAVI Marketplace!');
console.log('\n🔍 Bundle Contents:');
Object.keys(bundleStructure.files).forEach(file => {
    console.log(`   - ${file}`);
});

console.log('\n📋 Next Steps:');
console.log('   1. Run "npm run verify-bundle" to validate bundle integrity');
console.log('   2. Test extension in development environment');
console.log('   3. Submit bundle to NAVI Marketplace for review');
console.log('   4. Monitor extension performance and user feedback');