from ..types import PlannerRequest, PlannerResponse, PlannerStep
from ..intents import Intent

def plan_fix_problems(request: PlannerRequest) -> PlannerResponse:
    """First real plan - not intelligent yet, but correct, traceable, repeatable"""
    return PlannerResponse(
        intent=Intent.FIX_PROBLEMS,
        steps=[
            PlannerStep(
                tool="scanProblems",
                reason="Collect diagnostics from VS Code Problems tab"
            ),
            PlannerStep(
                tool="analyzeProblems", 
                reason="Group and prioritize errors by severity and file"
            ),
            PlannerStep(
                tool="applyFixes",
                reason="Apply safe deterministic fixes (no AI yet)"
            ),
            PlannerStep(
                tool="verifyProblems",
                reason="Re-scan diagnostics to confirm fixes"
            )
        ]
    )