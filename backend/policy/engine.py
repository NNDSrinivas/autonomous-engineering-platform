"""Policy enforcement engine for checking actions against org policies"""
import fnmatch
import json
import shlex
import os
from typing import Dict, List, Any


def _as_list(x: Any) -> List:
    """Convert various inputs to list format"""
    if not x:
        return []
    if isinstance(x, list):
        return x
    if isinstance(x, str) and x.strip().startswith('['):
        try:
            return json.loads(x)
        except json.JSONDecodeError:
            return []
    return []


def check_action(policy: Dict, action: Dict) -> Dict:
    """
    Check if an action is allowed by the organization policy.
    
    Args:
        policy: Dict containing org policy settings (from org_policy table)
        action: Dict describing the action to check with fields:
            - kind: str - Type of action (edit|cmd|git|pr|jira)
            - command: Optional[str] - Shell command being executed
            - files: Optional[List[str]] - Files being modified
            - repo: Optional[str] - Repository (org/repo format)
            - branch: Optional[str] - Git branch name
            - model: Optional[str] - LLM model name
            - phase: Optional[str] - Execution phase (plan|code|review)
    
    Returns:
        Dict with:
            - allowed: bool - Whether action passes policy checks
            - reasons: List[str] - Reasons for denial (empty if allowed)
            - require_review: bool - Whether action requires approval workflow
    """
    reasons = []
    
    # Check model allow list
    models_allow = set(_as_list(policy.get("models_allow")))
    if action.get("model") and models_allow and action["model"] not in models_allow:
        reasons.append(f"model {action['model']} not allowed")
    
    # Check command allow/deny lists
    allow_cmds = set(_as_list(policy.get("commands_allow")))
    deny_cmds = set(_as_list(policy.get("commands_deny")))
    if action.get("command"):
        cmd = action["command"]
        # Safely tokenize the command to avoid simple bypasses like '/usr/bin/sudo' or 'env sudo'
        try:
            tokens = shlex.split(cmd)
        except Exception:
            tokens = cmd.split()

        # Helper: compare token basenames to patterns
        def token_matches_pattern(tok: str, pat: str) -> bool:
            if not tok:
                return False
            if tok == pat:
                return True
            if os.path.basename(tok) == pat:
                return True
            # allow prefix-style rules like 'git' matching 'git-commit'
            if os.path.basename(tok).startswith(pat):
                return True
            return False

        # Deny-check: if any token matches a deny pattern, deny immediately
        denied = any(token_matches_pattern(tok, d) for d in deny_cmds for tok in tokens)
        if denied:
            reasons.append(f"command denied: {cmd}")
        else:
            # Allow-check: if an allow list exists, require at least one token to match
            if allow_cmds:
                allowed = any(token_matches_pattern(tok, a) for a in allow_cmds for tok in tokens)
                if not allowed:
                    reasons.append(f"command not in allow list: {cmd}")
    
    # Check path allow list (glob patterns)
    paths_allow = _as_list(policy.get("paths_allow"))
    if action.get("files"):
        for f in action["files"]:
            if paths_allow and not any(fnmatch.fnmatch(f, pat) for pat in paths_allow):
                reasons.append(f"path not allowed: {f}")
    
    # Check repository allow list
    repos_allow = set(_as_list(policy.get("repos_allow")))
    if action.get("repo") and repos_allow and action["repo"] not in repos_allow:
        reasons.append(f"repo not allowed: {action['repo']}")
    
    # Check protected branches (supports glob patterns)
    branches_protected = _as_list(policy.get("branches_protected"))
    if action.get("branch") and any(fnmatch.fnmatch(action["branch"], pat) for pat in branches_protected):
        reasons.append(f"protected branch: {action['branch']}")
    
    # Check if this action kind requires review
    require_list = set(_as_list(policy.get("require_review_for")))
    require_review = action.get("kind") in require_list
    
    return {
        "allowed": len(reasons) == 0,
        "reasons": reasons,
        "require_review": require_review
    }


def check_budget(
    policy: Dict,
    phase: str,
    current_usage: Dict[str, float]
) -> Dict:
    """
    Check if current usage is within budget limits for a phase.
    
    Args:
        policy: Dict containing org policy settings
        phase: Execution phase (plan|code|review)
        current_usage: Dict with 'tokens' and 'usd' current usage
    
    Returns:
        Dict with:
            - within_budget: bool
            - limits: Dict with token and USD limits
            - current: Dict with current usage
            - reasons: List[str] - Reasons for budget violation
    """
    reasons = []
    budgets = {}
    
    phase_budgets_str = policy.get("phase_budgets")
    if phase_budgets_str:
        try:
            budgets = json.loads(phase_budgets_str) if isinstance(phase_budgets_str, str) else phase_budgets_str
        except json.JSONDecodeError:
            budgets = {}
    
    phase_limit = budgets.get(phase, {})
    token_limit = phase_limit.get("tokens")
    usd_limit = phase_limit.get("usd_per_day")
    
    if token_limit and current_usage.get("tokens", 0) > token_limit:
        reasons.append(f"Token budget exceeded for {phase}: {current_usage['tokens']} > {token_limit}")
    
    if usd_limit and current_usage.get("usd", 0) > usd_limit:
        reasons.append(f"Cost budget exceeded for {phase}: ${current_usage['usd']:.2f} > ${usd_limit:.2f}")
    
    return {
        "within_budget": len(reasons) == 0,
        "limits": {"tokens": token_limit, "usd_per_day": usd_limit},
        "current": current_usage,
        "reasons": reasons
    }
