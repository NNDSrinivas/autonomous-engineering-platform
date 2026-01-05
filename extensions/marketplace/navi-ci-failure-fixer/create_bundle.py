#!/usr/bin/env python3
"""
CI Failure Fixer Extension Bundle Creator and Signer

This script:
1. Creates the .navi-ext bundle from the extension source
2. Signs it with CORE trust level using NAVI's signing system
3. Verifies the signature works correctly
4. Prepares it for marketplace deployment
"""

import os
import sys
import json
import zipfile
import tempfile
from pathlib import Path
from datetime import datetime, timezone

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent / "../../../"))

from backend.extensions.signing_service import (
    ExtensionSigningService,
    ExtensionVerificationService,
    TrustLevel,
)


def create_extension_bundle():
    """Create and sign the CI Failure Fixer extension bundle"""

    print("🏗️  Creating CI Failure Fixer Extension Bundle...")

    # Initialize signing service
    signing_service = ExtensionSigningService()

    # Generate NAVI core signing key
    print("🔑 Generating NAVI core signing key...")
    core_private, core_public = signing_service.generate_signing_key()
    signing_service.load_core_key(core_private)
    print(f"   Core public key: {core_public[:32]}...")

    # Extension directory
    extension_dir = Path(__file__).parent

    # Read all extension files
    extension_files = {}

    # Define file patterns to include
    file_patterns = [
        "*.ts",
        "*.js",
        "*.json",
        "*.md",
        "ci/*.ts",
        "fixes/*.ts",
        "types.ts",
    ]

    for pattern in file_patterns:
        for file_path in extension_dir.glob(pattern):
            if file_path.is_file() and file_path.name != "test_ci_fixer.py":
                relative_path = file_path.relative_to(extension_dir)
                with open(file_path, "rb") as f:
                    extension_files[str(relative_path)] = f.read()
                print(f"   📄 Added: {relative_path}")

    # Update manifest with final metadata
    manifest_path = extension_dir / "manifest.json"
    with open("manifest.json", "r") as f:
        original_manifest = json.load(f)

    # Update manifest with final metadata - only use fields that ExtensionManifest supports
    manifest_data = {
        "id": original_manifest["id"],
        "name": original_manifest["name"],
        "version": original_manifest["version"],
        "author": original_manifest["author"],
        "permissions": original_manifest["permissions"],
        "entry": original_manifest["entry"],
        # Note: hash, trust, and created_at will be set by the signing service
    }

    # Replace the manifest.json in extension_files with the corrected version
    # Note: We remove manifest.json from extension_files since package_extension will create it
    if "manifest.json" in extension_files:
        del extension_files["manifest.json"]

    print(f"📋 Extension manifest:")
    print(f"   ID: {manifest_data['id']}")
    print(f"   Name: {manifest_data['name']}")
    print(f"   Version: {manifest_data['version']}")
    print(f"   Trust Level: CORE (will be set by signing service)")
    print(f"   Permissions: {', '.join(manifest_data['permissions'])}")

    # Create signed bundle
    print("🔏 Creating signed extension bundle...")
    bundle = signing_service.create_extension_bundle(
        manifest_data, extension_files, TrustLevel.CORE
    )

    print(f"   Bundle hash: {bundle.bundle_hash[:16]}...")
    print(f"   Signature: {bundle.signature[:32]}...")
    print(f"   Files: {len(bundle.files)}")

    # Package extension
    print("📦 Packaging extension...")
    bundle_bytes = signing_service.package_extension(bundle)

    # Save bundle
    bundle_path = extension_dir / f"{manifest_data['id']}.navi-ext"
    with open(bundle_path, "wb") as f:
        f.write(bundle_bytes)

    print(f"✅ Extension bundle created: {bundle_path}")
    print(f"   Size: {len(bundle_bytes):,} bytes")

    # Verify signature
    print("🔍 Verifying extension signature...")
    verification_service = ExtensionVerificationService(signing_service)

    try:
        verified_bundle = verification_service.verify_extension_bundle(bundle_bytes)
        print("✅ Signature verification successful!")
        print(f"   Verified ID: {verified_bundle.manifest.id}")
        print(f"   Verified trust: {verified_bundle.manifest.trust}")
        print(f"   Verified files: {len(verified_bundle.files)}")

    except Exception as e:
        print(f"❌ Signature verification failed: {e}")
        return False

    # Create signature file separately for inspection
    signature_path = extension_dir / f"{manifest_data['id']}.signature.sig"
    signature_data = {
        "signature": bundle.signature,
        "public_key": bundle.public_key,
        "algorithm": "Ed25519",
        "trust_level": "CORE",
        "signed_at": datetime.now(timezone.utc).isoformat(),
        "extension_id": manifest_data["id"],
        "version": manifest_data["version"],
    }

    with open(signature_path, "w") as f:
        json.dump(signature_data, f, indent=2)

    print(f"📝 Signature file created: {signature_path}")

    # Summary
    print("\n🎉 CI Failure Fixer Extension Successfully Created!")
    print("=" * 60)
    print(f"Extension Bundle: {bundle_path}")
    print(f"Signature File:   {signature_path}")
    print(f"Trust Level:      CORE (highest)")
    print(f"Cryptographic:    Ed25519 signature")
    print(f"Verification:     ✅ Passed")
    print("=" * 60)
    print("Ready for marketplace deployment! 🚀")

    return True


if __name__ == "__main__":
    success = create_extension_bundle()
    sys.exit(0 if success else 1)
