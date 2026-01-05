from typing import Dict, List, Any
from pydantic import BaseModel
from .intents import Intent


class PlannerRequest(BaseModel):
    intent: Intent
    context: Dict[str, Any]


class PlannerStep(BaseModel):
    tool: str
    reason: str


class PlannerResponse(BaseModel):
    intent: Intent
    steps: List[PlannerStep]
