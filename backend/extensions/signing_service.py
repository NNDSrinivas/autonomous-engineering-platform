"""
Ed25519-based Extension Signing Service - Phase 7.2
Production-grade cryptographic signing with zero-trust verification

This replaces the existing RSA system with faster, more secure Ed25519 signatures.
Implements the security model from Phase 7.2 specification.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import tempfile
import zipfile
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# Ed25519 cryptography
try:
    from nacl.signing import SigningKey, VerifyKey
    from nacl.encoding import Base64Encoder
    from nacl.exceptions import BadSignatureError

    NACL_AVAILABLE = True
except ImportError:
    NACL_AVAILABLE = False
    logging.warning("PyNaCl not available - Ed25519 signing disabled")

logger = logging.getLogger(__name__)


class TrustLevel(str, Enum):
    """Extension trust levels with enforcement capabilities"""

    CORE = "CORE"  # NAVI Root Key - all permissions
    VERIFIED = "VERIFIED"  # Vendor Key - limited permissions
    ORG_APPROVED = "ORG_APPROVED"  # Org Admin Key - org policy scoped
    UNTRUSTED = "UNTRUSTED"  # Blocked - no execution allowed


class ExtensionPermission(str, Enum):
    """Available extension permissions"""

    FIX_PROBLEMS = "FIX_PROBLEMS"
    ANALYZE_PROJECT = "ANALYZE_PROJECT"
    CI_ACCESS = "CI_ACCESS"
    DEPLOY = "DEPLOY"
    CLUSTER_READ = "CLUSTER_READ"
    WRITE_FILES = "WRITE_FILES"
    NETWORK_ACCESS = "NETWORK_ACCESS"
    EXECUTE_COMMANDS = "EXECUTE_COMMANDS"
    K8S_READ = "K8S_READ"
    K8S_LOGS = "K8S_LOGS"
    REPO_READ = "REPO_READ"
    REQUEST_APPROVAL = "REQUEST_APPROVAL"
    PROPOSE_ACTIONS = "PROPOSE_ACTIONS"


@dataclass
class ExtensionManifest:
    """Immutable extension manifest structure"""

    id: str
    name: str
    version: str
    author: str
    permissions: List[ExtensionPermission]
    entry: str
    hash: str
    trust: TrustLevel
    created_at: str

    def to_signable_bytes(self) -> bytes:
        """Convert manifest to canonical bytes for signing"""
        # Create deterministic JSON representation
        manifest_dict = asdict(self)
        # Sort keys for consistency
        canonical_json = json.dumps(
            manifest_dict, sort_keys=True, separators=(",", ":")
        )
        return canonical_json.encode("utf-8")


@dataclass
class ExtensionBundle:
    """Complete extension bundle with signature"""

    manifest: ExtensionManifest
    files: Dict[str, bytes]  # filename -> content
    signature: str
    public_key: str
    bundle_hash: str


class ExtensionSigningService:
    """Production Ed25519 extension signing service"""

    def __init__(self):
        if not NACL_AVAILABLE:
            raise RuntimeError("PyNaCl required for Ed25519 signing")

        # Trust level keys (in production, load from secure storage)
        self._core_private_key: Optional[SigningKey] = None
        self._vendor_private_key: Optional[SigningKey] = None
        self._trusted_public_keys: Dict[TrustLevel, Set[str]] = {
            TrustLevel.CORE: set(),
            TrustLevel.VERIFIED: set(),
            TrustLevel.ORG_APPROVED: set(),
        }

    def generate_signing_key(self) -> Tuple[str, str]:
        """Generate new Ed25519 key pair"""
        if not NACL_AVAILABLE:
            raise RuntimeError("PyNaCl not available")

        private_key = SigningKey.generate()
        public_key = private_key.verify_key

        return (
            private_key.encode(encoder=Base64Encoder).decode(),
            public_key.encode(encoder=Base64Encoder).decode(),
        )

    def load_core_key(self, private_key_b64: str) -> None:
        """Load NAVI core signing key"""
        self._core_private_key = SigningKey(
            private_key_b64.encode(), encoder=Base64Encoder
        )

        # Add core public key to trusted set
        public_key = self._core_private_key.verify_key.encode(
            encoder=Base64Encoder
        ).decode()
        self._trusted_public_keys[TrustLevel.CORE].add(public_key)
        logger.info(f"Core signing key loaded: {public_key[:16]}...")

    def load_vendor_key(self, private_key_b64: str) -> None:
        """Load vendor signing key"""
        self._vendor_private_key = SigningKey(
            private_key_b64.encode(), encoder=Base64Encoder
        )

        # Add vendor public key to trusted set
        public_key = self._vendor_private_key.verify_key.encode(
            encoder=Base64Encoder
        ).decode()
        self._trusted_public_keys[TrustLevel.VERIFIED].add(public_key)
        logger.info(f"Vendor signing key loaded: {public_key[:16]}...")

    def add_trusted_key(self, trust_level: TrustLevel, public_key_b64: str) -> None:
        """Add trusted public key for trust level"""
        self._trusted_public_keys[trust_level].add(public_key_b64)
        logger.info(f"Added trusted key for {trust_level}: {public_key_b64[:16]}...")

    def hash_extension_bundle(self, files: Dict[str, bytes]) -> str:
        """Create SHA-256 hash of extension bundle"""
        # Create deterministic hash by sorting filenames
        hasher = hashlib.sha256()

        for filename in sorted(files.keys()):
            hasher.update(filename.encode("utf-8"))
            hasher.update(files[filename])

        return hasher.hexdigest()

    def create_extension_bundle(
        self,
        manifest_data: Dict[str, Any],
        files: Dict[str, bytes],
        trust_level: TrustLevel = TrustLevel.VERIFIED,
    ) -> ExtensionBundle:
        """Create signed extension bundle"""

        # Calculate bundle hash
        bundle_hash = self.hash_extension_bundle(files)

        # Create manifest with hash
        manifest = ExtensionManifest(
            id=manifest_data["id"],
            name=manifest_data["name"],
            version=manifest_data["version"],
            author=manifest_data["author"],
            permissions=[ExtensionPermission(p) for p in manifest_data["permissions"]],
            entry=manifest_data["entry"],
            hash=bundle_hash,
            trust=trust_level,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        # Sign manifest
        signature, public_key = self._sign_manifest(manifest, trust_level)

        return ExtensionBundle(
            manifest=manifest,
            files=files,
            signature=signature,
            public_key=public_key,
            bundle_hash=bundle_hash,
        )

    def _sign_manifest(
        self, manifest: ExtensionManifest, trust_level: TrustLevel
    ) -> Tuple[str, str]:
        """Sign extension manifest with appropriate key"""

        # Choose signing key based on trust level
        if trust_level == TrustLevel.CORE:
            if not self._core_private_key:
                raise RuntimeError("Core signing key not loaded")
            signing_key = self._core_private_key
        elif trust_level == TrustLevel.VERIFIED:
            if not self._vendor_private_key:
                raise RuntimeError("Vendor signing key not loaded")
            signing_key = self._vendor_private_key
        else:
            raise ValueError(f"Cannot sign with trust level: {trust_level}")

        # Sign canonical manifest bytes
        signable_bytes = manifest.to_signable_bytes()
        signed = signing_key.sign(signable_bytes)

        signature = base64.b64encode(signed.signature).decode()
        public_key = signing_key.verify_key.encode(encoder=Base64Encoder).decode()

        logger.info(f"Extension {manifest.id} signed with {trust_level} key")
        return signature, public_key

    def package_extension(self, bundle: ExtensionBundle) -> bytes:
        """Package extension bundle into .navi-ext format"""

        with tempfile.NamedTemporaryFile() as tmp_file:
            with zipfile.ZipFile(tmp_file.name, "w", zipfile.ZIP_DEFLATED) as zf:
                # Add manifest
                manifest_json = json.dumps(asdict(bundle.manifest), indent=2)
                zf.writestr("manifest.json", manifest_json)

                # Add signature file
                signature_data = {
                    "signature": bundle.signature,
                    "public_key": bundle.public_key,
                    "algorithm": "Ed25519",
                    "signed_at": datetime.now(timezone.utc).isoformat(),
                }
                zf.writestr("signature.sig", json.dumps(signature_data, indent=2))

                # Add extension files
                for filename, content in bundle.files.items():
                    zf.writestr(filename, content)

            tmp_file.seek(0)
            return tmp_file.read()


class ExtensionVerificationService:
    """Runtime verification service - zero trust enforcement"""

    def __init__(self, signing_service: ExtensionSigningService):
        self.signing_service = signing_service

    def verify_extension_bundle(self, bundle_bytes: bytes) -> ExtensionBundle:
        """Verify extension bundle integrity and signature"""

        # Extract bundle contents
        with tempfile.NamedTemporaryFile() as tmp_file:
            tmp_file.write(bundle_bytes)
            tmp_file.flush()

            try:
                with zipfile.ZipFile(tmp_file.name, "r") as zf:
                    # Read manifest
                    manifest_data = json.loads(zf.read("manifest.json").decode())
                    manifest = ExtensionManifest(**manifest_data)

                    # Read signature
                    signature_data = json.loads(zf.read("signature.sig").decode())
                    signature = signature_data["signature"]
                    public_key = signature_data["public_key"]

                    # Read extension files
                    files = {}
                    for filename in zf.namelist():
                        if filename not in ["manifest.json", "signature.sig"]:
                            files[filename] = zf.read(filename)

            except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as e:
                raise ValueError(f"Invalid extension bundle format: {e}")

        # Verify bundle hash
        expected_hash = manifest.hash
        actual_hash = self.signing_service.hash_extension_bundle(files)

        if actual_hash != expected_hash:
            raise ValueError(
                f"Extension bundle hash mismatch: expected {expected_hash}, got {actual_hash}"
            )

        # Verify signature
        self._verify_signature(manifest, signature, public_key)

        # Create verified bundle
        bundle = ExtensionBundle(
            manifest=manifest,
            files=files,
            signature=signature,
            public_key=public_key,
            bundle_hash=actual_hash,
        )

        logger.info(f"Extension {manifest.id} verified successfully")
        return bundle

    def _verify_signature(
        self, manifest: ExtensionManifest, signature: str, public_key: str
    ) -> None:
        """Verify Ed25519 signature"""

        try:
            verify_key = VerifyKey(public_key.encode(), encoder=Base64Encoder)
            signature_bytes = base64.b64decode(signature)
            signable_bytes = manifest.to_signable_bytes()

            verify_key.verify(signable_bytes, signature_bytes)

        except (BadSignatureError, ValueError) as e:
            raise ValueError(f"Invalid signature: {e}")

        # Verify public key is trusted for this trust level
        trust_level = manifest.trust
        trusted_keys = self.signing_service._trusted_public_keys.get(trust_level, set())

        if public_key not in trusted_keys:
            raise ValueError(
                f"Untrusted public key for {trust_level}: {public_key[:16]}..."
            )

        logger.info(f"Signature verified for {trust_level} extension {manifest.id}")


class OrganizationPolicy:
    """Organization-level extension policy enforcement"""

    def __init__(self):
        # Default policies (load from config in production)
        self.forbidden_permissions = {ExtensionPermission.DEPLOY}
        self.requires_approval = {
            ExtensionPermission.CI_ACCESS,
            ExtensionPermission.EXECUTE_COMMANDS,
        }
        self.blocked_authors = set()
        self.allowed_trust_levels = {
            TrustLevel.CORE,
            TrustLevel.VERIFIED,
            TrustLevel.ORG_APPROVED,
        }

    def validate_extension(self, manifest: ExtensionManifest) -> None:
        """Validate extension against organization policy"""

        # Check trust level
        if manifest.trust not in self.allowed_trust_levels:
            raise PermissionError(
                f"Trust level {manifest.trust} not allowed by org policy"
            )

        # Check forbidden permissions
        forbidden = set(manifest.permissions) & self.forbidden_permissions
        if forbidden:
            raise PermissionError(f"Forbidden permissions: {forbidden}")

        # Check blocked authors
        if manifest.author in self.blocked_authors:
            raise PermissionError(f"Author {manifest.author} is blocked")

        # Log approval requirements
        requires_approval = set(manifest.permissions) & self.requires_approval
        if requires_approval:
            logger.warning(
                f"Extension {manifest.id} requires approval for: {requires_approval}"
            )

        logger.info(f"Extension {manifest.id} passed organization policy validation")


# Global service instances (initialize with proper keys in production)
_signing_service: Optional[ExtensionSigningService] = None
_verification_service: Optional[ExtensionVerificationService] = None
_org_policy: Optional[OrganizationPolicy] = None


def get_signing_service() -> ExtensionSigningService:
    """Get global signing service instance"""
    global _signing_service
    if _signing_service is None:
        _signing_service = ExtensionSigningService()
    return _signing_service


def get_verification_service() -> ExtensionVerificationService:
    """Get global verification service instance"""
    global _verification_service
    if _verification_service is None:
        _verification_service = ExtensionVerificationService(get_signing_service())
    return _verification_service


def get_org_policy() -> OrganizationPolicy:
    """Get global organization policy instance"""
    global _org_policy
    if _org_policy is None:
        _org_policy = OrganizationPolicy()
    return _org_policy
