"""Prometheus metrics for policy enforcement and change reviews"""
from prometheus_client import Counter

# Policy check metrics
policy_checks_total = Counter(
    'aep_policy_checks_total',
    'Total number of policy checks performed',
    ['result', 'kind', 'org_id']
)

# Change request metrics
change_requests_total = Counter(
    'aep_change_requests_total',
    'Total number of change requests submitted',
    ['status', 'org_id']
)

# Change review metrics
change_reviews_total = Counter(
    'aep_change_reviews_total',
    'Total number of change reviews performed',
    ['decision', 'org_id']
)

# Budget violation metrics
budget_violations_total = Counter(
    'aep_budget_violations_total',
    'Total number of budget limit violations',
    ['phase', 'limit_type', 'org_id']
)


def record_policy_check(result: str, kind: str, org_id: str = "default"):
    """
    Record a policy check operation.
    
    Args:
        result: 'allow' or 'deny'
        kind: Action kind (edit|cmd|git|pr|jira)
        org_id: Organization identifier
    """
    policy_checks_total.labels(result=result, kind=kind, org_id=org_id).inc()


def record_change_request(status: str, org_id: str = "default"):
    """
    Record a change request submission.
    
    Args:
        status: 'pending', 'approved', or 'rejected'
        org_id: Organization identifier
    """
    change_requests_total.labels(status=status, org_id=org_id).inc()


def record_change_review(decision: str, org_id: str = "default"):
    """
    Record a change review decision.
    
    Args:
        decision: 'approve' or 'reject'
        org_id: Organization identifier
    """
    change_reviews_total.labels(decision=decision, org_id=org_id).inc()


def record_budget_violation(phase: str, limit_type: str, org_id: str = "default"):
    """
    Record a budget limit violation.
    
    Args:
        phase: Execution phase (plan|code|review)
        limit_type: 'tokens' or 'usd'
        org_id: Organization identifier
    """
    budget_violations_total.labels(phase=phase, limit_type=limit_type, org_id=org_id).inc()
