from .types import PlannerRequest, PlannerResponse
from .intents import Intent
from .plans.fix_problems_plan import plan_fix_problems

def run_planner(request: PlannerRequest) -> PlannerResponse:
    """Main planner entry point with strict validation"""
    validate_planner_request(request)
    
    if request.intent == Intent.FIX_PROBLEMS:
        return plan_fix_problems(request)
    else:
        raise ValueError(f"Unsupported intent: {request.intent}")
        
def validate_planner_request(request: PlannerRequest) -> None:
    """Fail fast validation - no silent planner nonsense"""
    if not request.intent:
        raise ValueError("PlannerRequest.intent is required")
        
    if request.intent not in Intent:
        raise ValueError(f"Invalid intent: {request.intent}")
        
    if not request.context.get('workspaceRoot'):
        raise ValueError("context.workspaceRoot is required")
        
    if not request.context.get('userMessage'):
        raise ValueError("context.userMessage is required")