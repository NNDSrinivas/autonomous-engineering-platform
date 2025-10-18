from sqlalchemy import Column, Integer, String, DateTime, Numeric, Text
from sqlalchemy.sql import func
from .db import Base

# Database schema constants
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
