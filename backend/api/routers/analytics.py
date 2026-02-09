"""
Analytics API Router - Usage and metrics dashboards.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from backend.core.auth.deps import require_role
from backend.core.auth.models import Role, User
from backend.database.session import get_db
from backend.models.llm_metrics import LlmMetric, TaskMetric
from backend.models.telemetry_events import ErrorEvent

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _compute_range(days: int) -> Dict[str, Any]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    return {"days": days, "start": start, "end": end}


def _summarize_llm_metrics(
    db: Session,
    start: datetime,
    org_id: Optional[str],
    user_id: Optional[str],
) -> Dict[str, Any]:
    query = db.query(LlmMetric).filter(LlmMetric.created_at >= start)
    if org_id is not None:
        query = query.filter(LlmMetric.org_id == org_id)
    if user_id is not None:
        query = query.filter(LlmMetric.user_id == user_id)

    summary_row = query.with_entities(
        func.count(LlmMetric.id),
        func.coalesce(func.sum(LlmMetric.total_tokens), 0),
        func.coalesce(func.sum(LlmMetric.total_cost), 0.0),
        func.avg(LlmMetric.latency_ms),
        func.coalesce(func.sum(case((LlmMetric.status != "success", 1), else_=0)), 0),
    ).first()

    total_requests = int(summary_row[0] or 0)
    total_tokens = int(summary_row[1] or 0)
    total_cost = float(summary_row[2] or 0.0)
    avg_latency = float(summary_row[3] or 0.0) if summary_row[3] is not None else None
    error_count = int(summary_row[4] or 0)
    error_rate = (error_count / total_requests) if total_requests else 0.0

    models = (
        query.with_entities(
            LlmMetric.model,
            func.count(LlmMetric.id),
            func.coalesce(func.sum(LlmMetric.total_tokens), 0),
            func.coalesce(func.sum(LlmMetric.total_cost), 0.0),
        )
        .group_by(LlmMetric.model)
        .order_by(func.sum(LlmMetric.total_tokens).desc())
        .all()
    )

    model_breakdown = [
        {
            "model": row[0],
            "requests": int(row[1] or 0),
            "tokens": int(row[2] or 0),
            "cost": float(row[3] or 0.0),
        }
        for row in models
    ]

    # Use dialect-appropriate date truncation (PostgreSQL vs SQLite)
    # Use get_bind() to safely get the engine (db.bind can be None)
    bind = db.get_bind()
    dialect = bind.dialect.name if bind else "sqlite"

    if dialect == "postgresql":
        day_column = func.date_trunc("day", LlmMetric.created_at).label("day")
    else:
        # SQLite and other dialects: use date() function to truncate to day
        day_column = func.date(LlmMetric.created_at).label("day")

    daily_rows = (
        query.with_entities(
            day_column,
            func.coalesce(func.sum(LlmMetric.total_tokens), 0),
            func.coalesce(func.sum(LlmMetric.total_cost), 0.0),
        )
        .group_by(day_column)
        .order_by(day_column)
        .all()
    )
    # Parse dates per dialect (PostgreSQL returns datetime, SQLite returns string)
    daily = []
    for row in daily_rows:
        raw_day = row[0]
        if raw_day is None:
            date_str = None
        elif hasattr(raw_day, "date"):
            # PostgreSQL: date_trunc returns datetime with .date() method
            date_str = raw_day.date().isoformat()
        else:
            # SQLite: func.date() returns string like "YYYY-MM-DD"
            date_str = str(raw_day)

        daily.append(
            {
                "date": date_str,
                "tokens": int(row[1] or 0),
                "cost": float(row[2] or 0.0),
            }
        )

    return {
        "summary": {
            "requests": total_requests,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "avg_latency_ms": avg_latency,
            "error_rate": error_rate,
            "error_count": error_count,
        },
        "models": model_breakdown,
        "daily": daily,
    }


def _summarize_tasks(
    db: Session,
    start: datetime,
    org_id: Optional[str],
    user_id: Optional[str],
) -> List[Dict[str, Any]]:
    query = db.query(TaskMetric).filter(TaskMetric.created_at >= start)
    if org_id is not None:
        query = query.filter(TaskMetric.org_id == org_id)
    if user_id is not None:
        query = query.filter(TaskMetric.user_id == user_id)

    rows = (
        query.with_entities(TaskMetric.status, func.count(TaskMetric.id))
        .group_by(TaskMetric.status)
        .all()
    )
    return [{"status": row[0], "count": int(row[1] or 0)} for row in rows]


def _summarize_errors(
    db: Session,
    start: datetime,
    org_id: Optional[str],
    user_id: Optional[str],
) -> List[Dict[str, Any]]:
    query = db.query(ErrorEvent).filter(ErrorEvent.created_at >= start)
    if org_id is not None:
        query = query.filter(ErrorEvent.org_id == org_id)
    if user_id is not None:
        query = query.filter(ErrorEvent.user_id == user_id)

    rows = (
        query.with_entities(ErrorEvent.severity, func.count(ErrorEvent.id))
        .group_by(ErrorEvent.severity)
        .all()
    )
    return [{"severity": row[0], "count": int(row[1] or 0)} for row in rows]


@router.get("/usage")
def usage_dashboard(
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    # TODO: Add tests for multi-tenant scoping and dialect-dependent date truncation
    # Required coverage:
    # 1. Verify org_id/user_id filtering prevents cross-tenant data leakage
    # 2. Test daily grouping output for both Postgres (date_trunc) and SQLite (date)
    # 3. Validate date string parsing for SQLite mode
    # 4. Test edge cases: empty data, single day, year boundary
    range_info = _compute_range(days)
    # Defensive attribute access for user identifier (support both user_id and id)
    user_id = getattr(user, "user_id", None) or getattr(user, "id", None)
    if user_id is None:
        raise HTTPException(status_code=500, detail="User identifier is not available")

    # Extract org identifier for multi-tenant data isolation (support org_id and org_key)
    org_id = getattr(user, "org_id", None) or getattr(user, "org_key", None)

    llm = _summarize_llm_metrics(db, range_info["start"], org_id, user_id)
    tasks = _summarize_tasks(db, range_info["start"], org_id, user_id)
    errors = _summarize_errors(db, range_info["start"], org_id, user_id)

    return {
        "scope": "user",
        "range": {
            "days": days,
            "start": range_info["start"].isoformat(),
            "end": range_info["end"].isoformat(),
        },
        **llm,
        "tasks": tasks,
        "errors": errors,
    }


@router.get("/org")
def org_dashboard(
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    # TODO: Add tests for multi-tenant scoping and dialect-dependent date truncation
    # Required coverage:
    # 1. Verify org_id filtering prevents cross-tenant data leakage
    # 2. Test daily grouping output for both Postgres (date_trunc) and SQLite (date)
    # 3. Validate date string parsing for SQLite mode
    # 4. Test edge cases: empty data, single day, year boundary
    # 5. Verify ADMIN role requirement
    range_info = _compute_range(days)

    # Derive org consistently using getattr to handle different User implementations
    # Fail closed if no org context is available to prevent cross-tenant data leakage
    org_id = getattr(user, "org_id", None) or getattr(user, "org_key", None)
    if not org_id:
        raise HTTPException(
            status_code=401, detail="Organization context required for org dashboard"
        )

    llm = _summarize_llm_metrics(db, range_info["start"], org_id, None)
    tasks = _summarize_tasks(db, range_info["start"], org_id, None)
    errors = _summarize_errors(db, range_info["start"], org_id, None)

    top_users = (
        db.query(
            LlmMetric.user_id,
            func.coalesce(func.sum(LlmMetric.total_tokens), 0),
            func.coalesce(func.sum(LlmMetric.total_cost), 0.0),
            func.count(LlmMetric.id),
        )
        .filter(LlmMetric.created_at >= range_info["start"])
        .filter(LlmMetric.org_id == org_id)
        .group_by(LlmMetric.user_id)
        .order_by(func.sum(LlmMetric.total_tokens).desc())
        .limit(10)
        .all()
    )
    users = [
        {
            "user_id": row[0],
            "tokens": int(row[1] or 0),
            "cost": float(row[2] or 0.0),
            "requests": int(row[3] or 0),
        }
        for row in top_users
    ]

    return {
        "scope": "org",
        "range": {
            "days": days,
            "start": range_info["start"].isoformat(),
            "end": range_info["end"].isoformat(),
        },
        **llm,
        "tasks": tasks,
        "errors": errors,
        "top_users": users,
    }
