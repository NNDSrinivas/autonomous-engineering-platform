"""Extension security tables - Phase 7.0

Revision ID: 0021_extension_security
Revises: 0025_governance_phase51
Create Date: 2025-12-25

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision = "0021_extension_security"
down_revision = "0025_governance_phase51"
branch_labels = None
depends_on = None


def upgrade():
    """Add extension security tables"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if (
        "extension_certificates" in existing_tables
        and "extension_signing_certificates" not in existing_tables
    ):
        op.rename_table("extension_certificates", "extension_signing_certificates")

    # Extension Security Reports table
    op.create_table(
        "extension_security_reports",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("extension_id", sa.String(255), nullable=False, index=True),
        sa.Column("report_id", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("security_level", sa.String(50), nullable=False),
        sa.Column("overall_score", sa.Integer, nullable=False),
        sa.Column("findings_count", sa.Integer, nullable=False),
        sa.Column("critical_findings", sa.Integer, nullable=False),
        sa.Column("high_findings", sa.Integer, nullable=False),
        sa.Column("has_certificate", sa.Boolean, nullable=False, default=False),
        sa.Column("policy_compliant", sa.Boolean, nullable=False, default=False),
        sa.Column("report_data", sa.JSON, nullable=False),
        sa.Column("tenant_id", sa.String(255), nullable=False, index=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # Extension Certificates table
    op.create_table(
        "extension_certificates",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "certificate_id", sa.String(255), nullable=False, unique=True, index=True
        ),
        sa.Column("extension_id", sa.String(255), nullable=False, index=True),
        sa.Column("issuer", sa.String(500), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_self_signed", sa.Boolean, nullable=False, default=False),
        sa.Column(
            "revocation_status", sa.String(50), nullable=False, default="unknown"
        ),
        sa.Column("certificate_data", sa.JSON, nullable=False),
        sa.Column("tenant_id", sa.String(255), nullable=False, index=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # Extension Security Policies table
    op.create_table(
        "extension_security_policies",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("tenant_id", sa.String(255), nullable=False, index=True),
        sa.Column("policy_name", sa.String(255), nullable=False),
        sa.Column("policy_value", sa.JSON, nullable=False),
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
    )

    # Create indexes for better query performance
    op.create_index(
        "idx_security_reports_extension_tenant",
        "extension_security_reports",
        ["extension_id", "tenant_id"],
    )

    op.create_index(
        "idx_security_reports_score_level",
        "extension_security_reports",
        ["overall_score", "security_level"],
    )

    op.create_index(
        "idx_certificates_extension_tenant",
        "extension_certificates",
        ["extension_id", "tenant_id"],
    )

    op.create_index(
        "idx_certificates_validity",
        "extension_certificates",
        ["valid_from", "valid_until"],
    )

    op.create_index(
        "idx_policies_tenant_name",
        "extension_security_policies",
        ["tenant_id", "policy_name"],
    )

    # Add comments for sensitive data (PostgreSQL only)
    if bind.dialect.name == "postgresql":
        op.execute(
            """COMMENT ON COLUMN extension_certificates.certificate_data IS 'SENSITIVE: Contains private keys and certificate data. Must be encrypted at rest in production.'"""
        )
        op.execute(
            """COMMENT ON TABLE extension_security_reports IS 'Extension security scan results and vulnerability assessments'"""
        )
        op.execute(
            """COMMENT ON TABLE extension_certificates IS 'Extension signing certificates and digital signatures'"""
        )
        op.execute(
            """COMMENT ON TABLE extension_security_policies IS 'Per-tenant security policies for extension validation'"""
        )
    else:
        logger.info(
            "Skipping column comments for %s database (PostgreSQL-specific feature)",
            bind.dialect.name,
        )


def downgrade():
    """Remove extension security tables"""

    # Drop indexes first
    op.drop_index("idx_policies_tenant_name", "extension_security_policies")
    op.drop_index("idx_certificates_validity", "extension_certificates")
    op.drop_index("idx_certificates_extension_tenant", "extension_certificates")
    op.drop_index("idx_security_reports_score_level", "extension_security_reports")
    op.drop_index("idx_security_reports_extension_tenant", "extension_security_reports")

    # Drop tables
    op.drop_table("extension_security_policies")
    op.drop_table("extension_certificates")
    op.drop_table("extension_security_reports")
