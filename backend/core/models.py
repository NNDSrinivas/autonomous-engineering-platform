from sqlalchemy import Column, Integer, String, DateTime, Numeric, Text, ForeignKey
from sqlalchemy.sql import func
from .db import Base

# Database schema constants
# Cost tracking uses 12,6 precision: supports up to $999,999.999999 per call
# with 6 decimal places for precise billing (e.g., $0.000001 per token)
COST_PRECISION = 12  # Total digits for cost_usd
COST_SCALE = 6  # Decimal places for cost_usd


class LLMCall(Base):
    __tablename__ = "llm_call"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    phase = Column(String(32), nullable=False)
    model = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False)  # ok|error
    prompt_hash = Column(String(64))
    tokens = Column(Integer)
    cost_usd = Column(Numeric(COST_PRECISION, COST_SCALE))
    latency_ms = Column(Integer)
    error_message = Column(Text)
    org_id = Column(String(64))
    user_id = Column(String(64))


class Org(Base):
    """Organization for RBAC and policy management"""

    __tablename__ = "org"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)


class OrgUser(Base):
    """User membership in organizations with assigned roles"""

    __tablename__ = "org_user"

    id = Column(Integer, primary_key=True)
    org_id = Column(String(64), ForeignKey("org.id"), nullable=False)
    user_id = Column(String(64), nullable=False)
    role = Column(String(16), nullable=False)  # admin|maintainer|developer|viewer


class OrgPolicy(Base):
    """Organization-level policies for access control and guardrails"""

    __tablename__ = "org_policy"

    org_id = Column(String(64), ForeignKey("org.id"), primary_key=True)
    models_allow = Column(Text)  # JSON array of allowed model names
    phase_budgets = Column(Text)  # JSON {plan,code,review:{tokens,usd_per_day}}
    commands_allow = Column(Text)  # JSON array of allowed shell commands
    commands_deny = Column(Text)  # JSON array of denied shell commands
    paths_allow = Column(Text)  # JSON array of allowed file path globs
    repos_allow = Column(Text)  # JSON array of allowed org/repo strings
    branches_protected = Column(Text)  # JSON array of protected branch names
    required_reviewers = Column(Integer)  # Number of required approvals
    require_review_for = Column(Text)  # JSON array of action kinds requiring review


class ChangeRequest(Base):
    """Change requests submitted for approval before execution"""

    __tablename__ = "change_request"

    id = Column(Integer, primary_key=True)
    org_id = Column(String(64), ForeignKey("org.id"), nullable=False)
    user_id = Column(String(64), nullable=False)
    ticket_key = Column(String(64))
    title = Column(String(256))
    plan_json = Column(Text, nullable=False)  # JSON of proposed steps
    patch_summary = Column(Text)  # Optional unified diff preview
    status = Column(
        String(16), nullable=False, server_default="pending"
    )  # pending|approved|rejected
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ChangeReview(Base):
    """Reviews (approve/reject) for change requests"""

    __tablename__ = "change_review"

    id = Column(Integer, primary_key=True)
    change_id = Column(Integer, ForeignKey("change_request.id", ondelete="CASCADE"))
    reviewer_id = Column(String(64), nullable=False)
    decision = Column(String(16), nullable=False)  # approve|reject
    comment = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
