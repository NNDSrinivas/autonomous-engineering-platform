"""Extension Platform - Phase 7.2 Database Schema

Revision ID: 0020_extension_platform
Revises: 0010_ext_connectors
Create Date: 2024-01-20 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "0020_extension_platform"
down_revision = "0010_ext_connectors"
branch_labels = None
depends_on = None


def upgrade():
    """Create extension platform tables"""

    # Extensions table - marketplace catalog
    op.create_table(
        "extensions",
        sa.Column(
            "id",
            sa.String(255),
            primary_key=True,
            comment="Extension ID (publisher.name format)",
        ),
        sa.Column("name", sa.String(255), nullable=False, comment="Display name"),
        sa.Column(
            "description", sa.Text, nullable=False, comment="Extension description"
        ),
        sa.Column(
            "version", sa.String(50), nullable=False, comment="Current version (semver)"
        ),
        # Author/Publisher info
        sa.Column(
            "author_name",
            sa.String(255),
            nullable=False,
            comment="Author or organization name",
        ),
        sa.Column(
            "author_verified",
            sa.Boolean,
            default=False,
            comment="Publisher verification status",
        ),
        sa.Column(
            "author_organization",
            sa.String(255),
            nullable=True,
            comment="Organization name if applicable",
        ),
        # Classification
        sa.Column(
            "category", sa.String(50), nullable=False, comment="Extension category"
        ),
        sa.Column("tags", sa.JSON, default=list, comment="Tags for discovery"),
        sa.Column("permissions", sa.JSON, default=list, comment="Required permissions"),
        sa.Column(
            "trust_level",
            sa.String(20),
            nullable=False,
            default="UNTRUSTED",
            comment="Trust level (CORE, VERIFIED, ORG_APPROVED, UNTRUSTED)",
        ),
        sa.Column(
            "capabilities", sa.JSON, default=list, comment="Extension capabilities"
        ),
        # Metrics
        sa.Column("downloads", sa.Integer, default=0, comment="Download count"),
        sa.Column("rating", sa.Float, default=0.0, comment="Average rating (0.0-5.0)"),
        sa.Column("review_count", sa.Integer, default=0, comment="Number of reviews"),
        # Metadata
        sa.Column(
            "icon_url", sa.String(500), nullable=True, comment="Extension icon URL"
        ),
        sa.Column(
            "homepage_url", sa.String(500), nullable=True, comment="Homepage URL"
        ),
        sa.Column(
            "repository_url",
            sa.String(500),
            nullable=True,
            comment="Source code repository",
        ),
        # Package info
        sa.Column(
            "package_url", sa.String(500), nullable=True, comment="Package download URL"
        ),
        sa.Column(
            "package_hash",
            sa.String(128),
            nullable=True,
            comment="Package SHA-256 hash",
        ),
        sa.Column(
            "signature",
            sa.Text,
            nullable=True,
            comment="RSA signature for trust verification",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "last_updated",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.CheckConstraint(
            "trust_level IN ('CORE', 'VERIFIED', 'ORG_APPROVED', 'UNTRUSTED')",
            name="check_trust_level",
        ),
        sa.CheckConstraint(
            "rating >= 0.0 AND rating <= 5.0", name="check_rating_range"
        ),
        sa.CheckConstraint("downloads >= 0", name="check_downloads_positive"),
    )

    # Extension installations - user/org specific installs
    op.create_table(
        "extension_installations",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
            comment="Installation ID",
        ),
        sa.Column(
            "extension_id",
            sa.String(255),
            nullable=False,
            comment="Reference to extensions.id",
        ),
        sa.Column(
            "user_id", sa.String(255), nullable=False, comment="User who installed"
        ),
        sa.Column(
            "org_id", sa.String(255), nullable=False, comment="Organization context"
        ),
        # Installation state
        sa.Column(
            "enabled", sa.Boolean, default=True, comment="Extension enabled status"
        ),
        sa.Column(
            "version_installed",
            sa.String(50),
            nullable=True,
            comment="Installed version",
        ),
        sa.Column(
            "installation_source",
            sa.String(50),
            default="marketplace",
            comment="How extension was installed",
        ),
        # Timestamps
        sa.Column(
            "installed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last usage timestamp",
        ),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["extension_id"], ["extensions.id"], ondelete="CASCADE"
        ),
        # Unique constraint - one installation per user/org/extension
        sa.UniqueConstraint(
            "extension_id",
            "user_id",
            "org_id",
            name="uq_installation_user_org_extension",
        ),
    )

    # Extension reviews and ratings
    op.create_table(
        "extension_reviews",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("extension_id", sa.String(255), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("org_id", sa.String(255), nullable=False),
        # Review content
        sa.Column("rating", sa.Integer, nullable=False, comment="Rating 1-5"),
        sa.Column("title", sa.String(255), nullable=True, comment="Review title"),
        sa.Column("content", sa.Text, nullable=True, comment="Review text"),
        sa.Column(
            "version_reviewed",
            sa.String(50),
            nullable=False,
            comment="Extension version reviewed",
        ),
        # Moderation
        sa.Column(
            "approved", sa.Boolean, default=True, comment="Review approval status"
        ),
        sa.Column(
            "flagged_count", sa.Integer, default=0, comment="Number of times flagged"
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["extension_id"], ["extensions.id"], ondelete="CASCADE"
        ),
        # Constraints
        sa.CheckConstraint(
            "rating >= 1 AND rating <= 5", name="check_review_rating_range"
        ),
        sa.UniqueConstraint(
            "extension_id", "user_id", "org_id", name="uq_review_user_org_extension"
        ),
    )

    # Extension signing certificates - for trust chain verification
    op.create_table(
        "extension_signing_certificates",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "certificate_name",
            sa.String(255),
            nullable=False,
            comment="Certificate identifier",
        ),
        sa.Column(
            "trust_level",
            sa.String(20),
            nullable=False,
            comment="Trust level this cert can sign",
        ),
        # Certificate data
        sa.Column(
            "public_key", sa.Text, nullable=False, comment="PEM-encoded public key"
        ),
        sa.Column(
            "private_key_path",
            sa.String(500),
            nullable=True,
            comment="Path to private key (for signing)",
        ),
        sa.Column(
            "algorithm", sa.String(50), default="RSA-PSS", comment="Signing algorithm"
        ),
        sa.Column("key_size", sa.Integer, default=2048, comment="Key size in bits"),
        # Certificate lifecycle
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Certificate expiration",
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Revocation timestamp",
        ),
        sa.Column(
            "revocation_reason",
            sa.String(255),
            nullable=True,
            comment="Reason for revocation",
        ),
        # Constraints
        sa.CheckConstraint(
            "trust_level IN ('CORE', 'VERIFIED', 'ORG_APPROVED')",
            name="check_cert_trust_level",
        ),
        sa.UniqueConstraint("certificate_name", name="uq_certificate_name"),
    )

    # Create indexes for performance
    op.create_index("idx_extensions_category", "extensions", ["category"])
    op.create_index("idx_extensions_trust_level", "extensions", ["trust_level"])
    op.create_index("idx_extensions_downloads", "extensions", ["downloads"])
    op.create_index("idx_extensions_rating", "extensions", ["rating"])
    op.create_index("idx_extensions_updated", "extensions", ["last_updated"])

    op.create_index(
        "idx_installations_user_org", "extension_installations", ["user_id", "org_id"]
    )
    op.create_index("idx_installations_enabled", "extension_installations", ["enabled"])

    op.create_index("idx_reviews_extension", "extension_reviews", ["extension_id"])
    op.create_index("idx_reviews_approved", "extension_reviews", ["approved"])


def downgrade():
    """Drop extension platform tables"""
    op.drop_table("extension_reviews")
    op.drop_table("extension_signing_certificates")
    op.drop_table("extension_installations")
    op.drop_table("extensions")
