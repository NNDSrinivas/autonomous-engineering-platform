from sqlalchemy import Column, Integer, String, DateTime, Numeric, Text
from sqlalchemy.sql import func
from .db import Base


class LLMCall(Base):
    __tablename__ = "llm_call"

    id = Column(Integer, primary_key=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    phase = Column(String(32), nullable=False)
    model = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False)  # ok|error
    prompt_hash = Column(String(64))
    tokens = Column(Integer)
    cost_usd = Column(Numeric(12, 6))
    latency_ms = Column(Integer)
    error_message = Column(Text)
    org_id = Column(String(64))
    user_id = Column(String(64))
