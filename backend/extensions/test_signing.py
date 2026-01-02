"""
Tests for Extension Signing System - Phase 7.2
Comprehensive tests for zero-trust extension security

These tests verify:
- ✅ Valid signed bundle → accepted
- ❌ Unsigned extension → rejected  
- ❌ Modified bundle → rejected
- ❌ Permission escalation → rejected
- ❌ Invalid signer → rejected
"""

import pytest
import json
import tempfile
import zipfile
from pathlib import Path

from backend.extensions.signing_service import (
    ExtensionSigningService,
    ExtensionVerificationService,
    ExtensionManifest,
    TrustLevel,
    ExtensionPermission
)
from backend.extensions.verify import (
    ExtensionVerifier,
    VerificationError
)
from backend.extensions.policy import (
    PolicyEngine,
    PolicyAction,
)

class TestExtensionSigning:
    """Test Ed25519 extension signing"""
    
    def setup_method(self):
        """Set up test environment"""
        self.signing_service = ExtensionSigningService()
        
        # Generate test keys
        core_private, core_public = self.signing_service.generate_signing_key()
        vendor_private, vendor_public = self.signing_service.generate_signing_key()
        
        # Load keys into service
        self.signing_service.load_core_key(core_private)
        self.signing_service.load_vendor_key(vendor_private)
        
        # Sample extension files
        self.test_files = {
            "index.js": b"console.log('CI Fixer Extension');",
            "package.json": b'{"name": "ci-fixer", "version": "1.0.0"}',
            "README.md": b"# CI Fixer Extension\\nFixes CI failures"
        }
        
        # Sample manifest data
        self.test_manifest = {
            "id": "navi-ci-fixer",
            "name": "CI Failure Fixer",
            "version": "1.0.0", 
            "author": "Navra Labs",
            "permissions": ["FIX_PROBLEMS", "CI_ACCESS"],
            "entry": "index.js"
        }
    
    def test_key_generation(self):
        """Test Ed25519 key generation"""
        private_key, public_key = self.signing_service.generate_signing_key()
        
        assert private_key is not None
        assert public_key is not None
        assert len(private_key) > 0
        assert len(public_key) > 0
        assert private_key != public_key
    
    def test_valid_extension_signing(self):
        """✅ Test valid extension signing and verification"""
        
        # Create signed bundle
        bundle = self.signing_service.create_extension_bundle(
            self.test_manifest,
            self.test_files,
            TrustLevel.VERIFIED
        )
        
        assert bundle.manifest.id == "navi-ci-fixer"
        assert bundle.manifest.trust == TrustLevel.VERIFIED
        assert bundle.signature is not None
        assert bundle.public_key is not None
        assert len(bundle.files) == 3
        
        # Package bundle
        bundle_bytes = self.signing_service.package_extension(bundle)
        assert len(bundle_bytes) > 0
        
        # Verify bundle
        verification_service = ExtensionVerificationService(self.signing_service)
        verified_bundle = verification_service.verify_extension_bundle(bundle_bytes)
        
        assert verified_bundle.manifest.id == bundle.manifest.id
        assert verified_bundle.signature == bundle.signature
        assert verified_bundle.bundle_hash == bundle.bundle_hash
    
    def test_unsigned_extension_rejection(self):
        """❌ Test unsigned extension rejection"""
        
        # Create bundle without signature
        with tempfile.NamedTemporaryFile(suffix='.zip') as tmp_file:
            with zipfile.ZipFile(tmp_file.name, 'w') as zf:
                # Add manifest without signature
                manifest = ExtensionManifest(
                    id="unsigned-extension",
                    name="Unsigned Extension",
                    version="1.0.0",
                    author="Unknown",
                    permissions=[ExtensionPermission.ANALYZE_PROJECT],
                    entry="index.js",
                    hash="fake-hash",
                    trust=TrustLevel.UNTRUSTED,
                    created_at="2025-12-25T00:00:00Z"
                )
                zf.writestr("manifest.json", json.dumps(manifest.__dict__))
                zf.writestr("index.js", "console.log('unsigned');")
            
            tmp_file.seek(0)
            bundle_bytes = tmp_file.read()
        
        # Verification should fail
        verification_service = ExtensionVerificationService(self.signing_service)
        with pytest.raises(ValueError, match="signature"):
            verification_service.verify_extension_bundle(bundle_bytes)
    
    def test_tampered_bundle_rejection(self):
        """❌ Test modified bundle rejection"""
        
        # Create valid signed bundle
        bundle = self.signing_service.create_extension_bundle(
            self.test_manifest,
            self.test_files,
            TrustLevel.VERIFIED
        )
        
        # Package it
        self.signing_service.package_extension(bundle)
        
        # Tamper with the bundle by modifying content
        tampered_files = self.test_files.copy()
        tampered_files["malicious.py"] = b"import os; os.system('rm -rf /')"
        
        tampered_bundle = self.signing_service.create_extension_bundle(
            self.test_manifest,
            tampered_files,  # Different files
            TrustLevel.VERIFIED
        )
        
        # Replace signature with original (simulating tampering)
        tampered_bundle.signature = bundle.signature
        tampered_bundle.public_key = bundle.public_key
        
        tampered_bytes = self.signing_service.package_extension(tampered_bundle)
        
        # Verification should fail due to hash mismatch
        verification_service = ExtensionVerificationService(self.signing_service)
        with pytest.raises(ValueError, match="Invalid signature"):
            verification_service.verify_extension_bundle(tampered_bytes)
    
    def test_untrusted_signer_rejection(self):
        """❌ Test invalid signer rejection"""
        
        # Create new signing service with different keys
        rogue_service = ExtensionSigningService()
        rogue_private, rogue_public = rogue_service.generate_signing_key()
        rogue_service.load_vendor_key(rogue_private)
        
        # Sign extension with rogue key
        rogue_bundle = rogue_service.create_extension_bundle(
            self.test_manifest,
            self.test_files,
            TrustLevel.VERIFIED
        )
        
        rogue_bytes = rogue_service.package_extension(rogue_bundle)
        
        # Verify with original service (different trusted keys)
        verification_service = ExtensionVerificationService(self.signing_service)
        with pytest.raises(ValueError, match="Untrusted public key"):
            verification_service.verify_extension_bundle(rogue_bytes)

class TestPolicyEnforcement:
    """Test policy enforcement system"""
    
    def setup_method(self):
        """Set up policy test environment"""
        self.policy_engine = PolicyEngine()
        
        # Sample manifests for testing
        self.safe_manifest = ExtensionManifest(
            id="safe-extension",
            name="Safe Extension",
            version="1.0.0",
            author="Trusted Author",
            permissions=[ExtensionPermission.ANALYZE_PROJECT],
            entry="index.js",
            hash="safe-hash",
            trust=TrustLevel.VERIFIED,
            created_at="2025-12-25T00:00:00Z"
        )
        
        self.dangerous_manifest = ExtensionManifest(
            id="dangerous-extension",
            name="Dangerous Extension",
            version="1.0.0",
            author="Unknown Author",
            permissions=[ExtensionPermission.DEPLOY, ExtensionPermission.EXECUTE_COMMANDS],
            entry="index.js",
            hash="danger-hash",
            trust=TrustLevel.UNTRUSTED,
            created_at="2025-12-25T00:00:00Z"
        )
    
    def test_untrusted_extension_blocked(self):
        """❌ Test untrusted extensions are blocked"""
        
        result = self.policy_engine.evaluate_installation(self.dangerous_manifest)
        
        assert result.action == PolicyAction.DENY
        assert "Untrusted extensions are blocked" in result.reason
    
    def test_safe_extension_allowed(self):
        """✅ Test safe extensions are allowed"""
        
        result = self.policy_engine.evaluate_installation(self.safe_manifest)
        
        assert result.action == PolicyAction.ALLOW
        assert "meets all policy requirements" in result.reason
    
    def test_permission_escalation_blocked(self):
        """❌ Test permission escalation attempts blocked"""
        
        # Create manifest requesting forbidden permissions
        escalation_manifest = ExtensionManifest(
            id="escalation-attempt",
            name="Escalation Extension",
            version="1.0.0",
            author="Trusted Author",
            permissions=[ExtensionPermission.DEPLOY],  # Forbidden by default org policy
            entry="index.js",
            hash="escalation-hash",
            trust=TrustLevel.VERIFIED,
            created_at="2025-12-25T00:00:00Z"
        )
        
        result = self.policy_engine.evaluate_installation(escalation_manifest)
        
        assert result.action == PolicyAction.DENY
        assert "forbidden permissions" in result.reason
    
    def test_approval_required_for_critical_permissions(self):
        """Test critical permissions require approval"""
        
        # Create manifest with permission requiring approval
        approval_manifest = ExtensionManifest(
            id="approval-required",
            name="Critical Extension",
            version="1.0.0",
            author="Trusted Author", 
            permissions=[ExtensionPermission.EXECUTE_COMMANDS],  # Requires approval
            entry="index.js",
            hash="critical-hash",
            trust=TrustLevel.VERIFIED,
            created_at="2025-12-25T00:00:00Z"
        )
        
        result = self.policy_engine.evaluate_installation(approval_manifest)
        
        assert result.action == PolicyAction.REQUIRE_APPROVAL
        assert "requires administrator approval" in result.reason

class TestCompleteVerificationFlow:
    """Test complete end-to-end verification flow"""
    
    def setup_method(self):
        """Set up complete test environment"""
        self.verifier = ExtensionVerifier()
    
    def test_complete_verification_success(self):
        """✅ Test complete verification flow success"""
        
        # This would use real signed bundle in production
        # For now, test the verification structure
        
        signing_service = ExtensionSigningService()
        core_private, core_public = signing_service.generate_signing_key()
        signing_service.load_core_key(core_private)
        
        # Create valid bundle
        test_files = {"index.js": b"console.log('valid extension');"}
        test_manifest = {
            "id": "test-valid-extension",
            "name": "Valid Test Extension", 
            "version": "1.0.0",
            "author": "Test Author",
            "permissions": ["ANALYZE_PROJECT"],
            "entry": "index.js"
        }
        
        bundle = signing_service.create_extension_bundle(
            test_manifest,
            test_files,
            TrustLevel.CORE  # Use CORE trust to bypass policy restrictions
        )
        
        bundle_bytes = signing_service.package_extension(bundle)
        
        # Create verifier with our signing service
        from backend.extensions.verify import ExtensionVerifier
        from backend.extensions.signing_service import ExtensionVerificationService
        
        verifier = ExtensionVerifier()
        verifier.verification_service = ExtensionVerificationService(signing_service)
        
        # Verify complete flow
        verified_bundle = verifier.verify_and_validate_extension(
            bundle_bytes=bundle_bytes,
            user_id="test-user",
            org_id="test-org"
        )
        
        assert verified_bundle.manifest.id == "test-valid-extension"
        assert verified_bundle.manifest.trust == TrustLevel.CORE
    
    def test_complete_verification_failure(self):
        """❌ Test complete verification flow failure"""
        
        # Create invalid bundle (empty bytes)
        invalid_bytes = b"invalid bundle data"
        
        with pytest.raises(VerificationError):
            self.verifier.verify_and_validate_extension(
                bundle_bytes=invalid_bytes,
                user_id="test-user", 
                org_id="test-org"
            )

if __name__ == "__main__":
    # Run tests
    import subprocess
    import sys
    
    result = subprocess.run([
        sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"
    ], cwd=Path(__file__).parent.parent.parent)
    
    sys.exit(result.returncode)