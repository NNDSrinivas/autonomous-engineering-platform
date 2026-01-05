from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor
import asyncio
import os

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.core.auth.deps import get_current_user_optional
from backend.services.org_ingestor import ingest_jira_for_user, ingest_confluence_space
from backend.services.slack_ingestor import ingest_slack
from backend.services.teams_ingestor import ingest_teams
from backend.services.zoom_ingestor import ingest_zoom_meetings

router = APIRouter(prefix="/api/org/scan", tags=["org-scan"])

_TABLE_READY = False
_SCAN_EXECUTOR = ThreadPoolExecutor(max_workers=2)


def _ensure_table(db: Session) -> None:
    """Create lightweight org scan table if it doesn't exist."""
    global _TABLE_READY
    if _TABLE_READY:
        return
    try:
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS navi_org_scan (
                    org_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    consent BOOLEAN DEFAULT FALSE,
                    allow_secrets BOOLEAN DEFAULT FALSE,
                    consent_at TIMESTAMPTZ,
                    paused_at TIMESTAMPTZ,
                    last_scan_at TIMESTAMPTZ,
                    summary TEXT,
                    state TEXT,
                    config_json JSONB,
                    PRIMARY KEY (org_id, user_id)
                )
                """
            )
        )
        # Ensure new columns exist on old tables
        db.execute(
            text(
                "ALTER TABLE navi_org_scan ADD COLUMN IF NOT EXISTS allow_secrets BOOLEAN DEFAULT FALSE"
            )
        )
        db.execute(
            text("ALTER TABLE navi_org_scan ADD COLUMN IF NOT EXISTS summary TEXT")
        )
        db.execute(
            text("ALTER TABLE navi_org_scan ADD COLUMN IF NOT EXISTS config_json JSONB")
        )
        db.commit()
        _TABLE_READY = True
    except Exception:
        db.rollback()
        # If creation fails, allow FastAPI to propagate a 500 later
        _TABLE_READY = False


def _upsert_state(
    db: Session,
    org_id: str,
    user_id: str,
    consent: Optional[bool] = None,
    allow_secrets: Optional[bool] = None,
    paused_at: Optional[datetime] = None,
    last_scan_at: Optional[datetime] = None,
    state: Optional[str] = None,
    summary: Optional[str] = None,
    config_json: Optional[dict] = None,
) -> None:
    _ensure_table(db)
    now = datetime.now(timezone.utc)
    db.execute(
        text(
            """
            INSERT INTO navi_org_scan (org_id, user_id, consent, allow_secrets, consent_at, paused_at, last_scan_at, state, summary, config_json)
            VALUES (:org_id, :user_id, :consent, :allow_secrets, :consent_at, :paused_at, :last_scan_at, :state, :summary, COALESCE(:config_json, '{}'::jsonb))
            ON CONFLICT (org_id, user_id) DO UPDATE
            SET
              consent = COALESCE(EXCLUDED.consent, navi_org_scan.consent),
              allow_secrets = COALESCE(EXCLUDED.allow_secrets, navi_org_scan.allow_secrets),
              consent_at = COALESCE(EXCLUDED.consent_at, navi_org_scan.consent_at),
              paused_at = COALESCE(EXCLUDED.paused_at, navi_org_scan.paused_at),
              last_scan_at = COALESCE(EXCLUDED.last_scan_at, navi_org_scan.last_scan_at),
              state = COALESCE(EXCLUDED.state, navi_org_scan.state),
              summary = COALESCE(EXCLUDED.summary, navi_org_scan.summary),
              config_json = COALESCE(EXCLUDED.config_json, navi_org_scan.config_json)
            """
        ),
        {
            "org_id": org_id,
            "user_id": user_id,
            "consent": consent,
            "allow_secrets": allow_secrets,
            "consent_at": now if consent else None,
            "paused_at": paused_at,
            "last_scan_at": last_scan_at,
            "state": state,
            "summary": summary,
            "config_json": config_json,
        },
    )
    db.commit()


def _get_state(db: Session, org_id: str, user_id: str) -> dict:
    _ensure_table(db)
    row = (
        db.execute(
            text(
                "SELECT org_id, user_id, consent, allow_secrets, consent_at, paused_at, last_scan_at, state, summary, config_json FROM navi_org_scan WHERE org_id = :org_id AND user_id = :user_id"
            ),
            {"org_id": org_id, "user_id": user_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else {}


def _get_config(db: Session, org_id: str, user_id: str) -> dict:
    state = _get_state(db, org_id, user_id)
    return state.get("config_json") or {}


def _resolve_ids(
    user, x_org_id: Optional[str], x_user_id: Optional[str]
) -> tuple[str, str]:
    org_id = getattr(user, "org_id", None) or (x_org_id or "default")
    user_id = getattr(user, "user_id", None) or (x_user_id or "default_user")
    return org_id, user_id


@router.post("/consent")
def give_consent(
    allow_secrets: bool = False,
    x_org_id: Optional[str] = Header(default=None, alias="X-Org-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    """
    Record user consent to scan the repo/org docs.
    allow_secrets=false means scanners must skip secret/keys paths.
    """
    org_id, user_id = _resolve_ids(user, x_org_id, x_user_id)
    _upsert_state(
        db, org_id, user_id, consent=True, allow_secrets=allow_secrets, state="ready"
    )
    return {"consent": True, "allow_secrets": allow_secrets}


@router.post("/revoke")
def revoke_consent(
    x_org_id: Optional[str] = Header(default=None, alias="X-Org-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    org_id, user_id = _resolve_ids(user, x_org_id, x_user_id)
    _upsert_state(db, org_id, user_id, consent=False, state="revoked")
    return {"consent": False}


@router.post("/pause")
def pause_scan(
    x_org_id: Optional[str] = Header(default=None, alias="X-Org-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    org_id, user_id = _resolve_ids(user, x_org_id, x_user_id)
    _upsert_state(
        db, org_id, user_id, paused_at=datetime.now(timezone.utc), state="paused"
    )
    return {"paused": True}


@router.post("/resume")
def resume_scan(
    x_org_id: Optional[str] = Header(default=None, alias="X-Org-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    org_id, user_id = _resolve_ids(user, x_org_id, x_user_id)
    _upsert_state(db, org_id, user_id, paused_at=None, state="ready")
    return {"paused": False}


@router.post("/config")
def save_scan_config(
    config: dict,
    x_org_id: Optional[str] = Header(default=None, alias="X-Org-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    """
    Persist org-scan ingestion config from the UI (connector panel).
    Expected keys: confluence_space_keys, slack_channels, teams, teams_channels, zoom_user,
    zoom_lookback_days, zoom_max_meetings.
    """
    org_id, user_id = _resolve_ids(user, x_org_id, x_user_id)
    # Normalize lists
    normalized = {}
    for key in ("confluence_space_keys", "slack_channels", "teams", "teams_channels"):
        val = config.get(key)
        if isinstance(val, str):
            normalized[key] = [x.strip() for x in val.split(",") if x.strip()]
        elif isinstance(val, list):
            normalized[key] = [str(x).strip() for x in val if str(x).strip()]
    # Scalars
    for key in ("zoom_user",):
        if key in config:
            normalized[key] = str(config.get(key) or "").strip()
    for key in ("zoom_lookback_days", "zoom_max_meetings"):
        if key in config:
            try:
                normalized[key] = int(config.get(key))
            except Exception:
                pass

    state = _get_state(db, org_id, user_id)
    merged = {**(state.get("config_json") or {}), **normalized}
    _upsert_state(db, org_id, user_id, config_json=merged)
    return {"ok": True, "config": merged}


@router.get("/config")
def get_scan_config(
    x_org_id: Optional[str] = Header(default=None, alias="X-Org-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    org_id, user_id = _resolve_ids(user, x_org_id, x_user_id)
    return {"config": _get_config(db, org_id, user_id)}


@router.post("/run")
def trigger_scan(
    include_secrets: bool = False,
    workspace_root: Optional[str] = None,
    x_org_id: Optional[str] = Header(default=None, alias="X-Org-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    """
    Trigger a lightweight repo/org scan (synchronous placeholder).
    """
    org_id, user_id = _resolve_ids(user, x_org_id, x_user_id)
    state = _get_state(db, org_id, user_id)
    if not state.get("consent"):
        raise HTTPException(status_code=403, detail="Consent required before scanning")
    if state.get("paused_at"):
        raise HTTPException(
            status_code=409, detail="Scanning is paused; resume before running"
        )

    allow_secrets = bool(state.get("allow_secrets"))
    effective_include_secrets = include_secrets and allow_secrets

    now = datetime.now(timezone.utc)
    _upsert_state(db, org_id, user_id, last_scan_at=None, state="in_progress")

    def _do_scan():
        local_db = next(get_db())
        try:
            summary = _scan_workspace(
                workspace_root or "",
                effective_include_secrets,
                local_db,
                user_id,
                requested_include_secrets=include_secrets,
                allow_secrets=allow_secrets,
                config=_get_config(local_db, org_id, user_id),
            )
            finished = datetime.now(timezone.utc)
            _upsert_state(
                local_db,
                org_id,
                user_id,
                last_scan_at=finished,
                state="completed",
                summary=summary,
            )
        except Exception as exc:  # noqa: BLE001
            _upsert_state(local_db, org_id, user_id, state=f"failed: {exc}")
        finally:
            try:
                local_db.close()
            except Exception:
                pass

    _SCAN_EXECUTOR.submit(_do_scan)

    return {
        "started": True,
        "include_secrets": effective_include_secrets,
        "queued_at": now,
    }


@router.get("/status")
def scan_status(
    x_org_id: Optional[str] = Header(default=None, alias="X-Org-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    org_id, user_id = _resolve_ids(user, x_org_id, x_user_id)
    return _get_state(db, org_id, user_id)


@router.post("/clear")
def clear_org_memory(
    x_org_id: Optional[str] = Header(default=None, alias="X-Org-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    """
    Clears scan metadata; does not remove other memories yet.
    """
    _ensure_table(db)
    org_id, user_id = _resolve_ids(user, x_org_id, x_user_id)
    db.execute(
        text("DELETE FROM navi_org_scan WHERE org_id = :org_id AND user_id = :user_id"),
        {"org_id": org_id, "user_id": user_id},
    )
    db.commit()
    return {"cleared": True}


# --- helpers ---------------------------------------------------------------


def _env_list(var_name: str) -> List[str]:
    raw = os.getenv(var_name, "") or ""
    return [item.strip() for item in raw.split(",") if item.strip()]


def _run_async(coro):
    """
    Run an async coroutine from a thread-safe context.
    """
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            try:
                loop.close()
            except Exception:
                pass


def _scan_workspace(
    root: str,
    include_secrets: bool,
    db,
    user_id: str,
    *,
    requested_include_secrets: bool = False,
    allow_secrets: bool = False,
    config: Optional[dict] = None,
) -> str:
    """
    Repository/doc scanner: lists key files, samples docs, and a small file tree summary.
    """
    import pathlib
    import json

    if not root:
        root = os.getcwd()

    root_path = pathlib.Path(root)
    if not root_path.exists():
        return f"Workspace root not found: {root}"

    excluded_dirs = {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".idea",
        ".vscode",
        "dist",
        "build",
        "out",
    }
    secret_like = {"secrets", "keys", ".ssh", ".aws", "config", ".env", ".env.local"}

    tree_lines = []
    max_entries = 200
    count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir == ".":
            rel_dir = ""

        # Filter dirs
        new_dirs = []
        for d in dirnames:
            if d in excluded_dirs:
                continue
            if not include_secrets and d in secret_like:
                continue
            new_dirs.append(d)
        dirnames[:] = new_dirs

        for fname in filenames:
            if not include_secrets:
                if any(
                    token in fname.lower()
                    for token in [
                        "secret",
                        "key",
                        ".pem",
                        ".p12",
                        ".crt",
                        ".env",
                        "config",
                    ]
                ):
                    continue
            path_rel = os.path.join(rel_dir, fname) if rel_dir else fname
            tree_lines.append(path_rel)
            count += 1
            if count >= max_entries:
                break
        if count >= max_entries:
            break

    key_files = []
    key_candidates = [
        "README.md",
        "package.json",
        "pyproject.toml",
        "pom.xml",
        "requirements.txt",
        "Cargo.toml",
    ]
    for candidate in key_candidates:
        p = root_path / candidate
        if p.exists():
            try:
                key_files.append({"path": candidate, "content": p.read_text()[:4000]})
            except Exception:
                continue

    # Sample docs folder
    docs_samples = []
    docs_dir = root_path / "docs"
    if docs_dir.exists() and docs_dir.is_dir():
        for dp in docs_dir.rglob("*"):
            if dp.is_file() and dp.suffix.lower() in {".md", ".txt"}:
                rel = dp.relative_to(root_path)
                try:
                    docs_samples.append(
                        {"path": str(rel), "content": dp.read_text()[:3000]}
                    )
                except Exception:
                    continue
                if len(docs_samples) >= 5:
                    break

    summary = []
    summary.append(f"Workspace root: {root_path}")
    summary.append(f"Files indexed (max {max_entries}): {count}")
    summary.append(
        f"Secrets requested={requested_include_secrets}, allowed={allow_secrets}, scanning_secrets={include_secrets}"
    )
    if tree_lines:
        summary.append("File list (sample):")
        summary.append("\n".join(tree_lines[:50]))
    if key_files:
        summary.append("\nKey files:")
        summary.append(json.dumps(key_files, indent=2))
    if docs_samples:
        summary.append("\nDocs samples:")
        summary.append(json.dumps(docs_samples, indent=2))

    # Jira snapshot (best-effort)
    try:
        jira_rows = (
            db.execute(
                text(
                    """
                SELECT issue_key, project_key, summary, status, assignee, updated
                FROM jira_issue
                ORDER BY updated DESC NULLS LAST
                LIMIT 20
                """
                )
            )
            .mappings()
            .all()
        )
        if jira_rows:
            summary.append("\nJira snapshot (latest 20):")
            summary.append(
                json.dumps([dict(r) for r in jira_rows], default=str, indent=2)
            )
    except Exception:
        summary.append("\nJira snapshot unavailable (query failed).")

    # Confluence / Slack / Zoom snapshot from navi_memory (workspace + interaction)
    try:
        mem_rows = (
            db.execute(
                text(
                    """
                SELECT category, title, content, meta_json, updated_at
                FROM navi_memory
                WHERE category IN ('workspace','interaction')
                ORDER BY updated_at DESC
                LIMIT 20
                """
                )
            )
            .mappings()
            .all()
        )
        if mem_rows:
            snapshot = []
            for r in mem_rows:
                snapshot.append(
                    {
                        "category": r.get("category"),
                        "title": r.get("title"),
                        "content": (r.get("content") or "")[:800],
                        "meta": r.get("meta_json"),
                        "updated_at": str(r.get("updated_at")),
                    }
                )
            summary.append("\nDocs/Comms snapshot (workspace/interaction memories):")
            summary.append(json.dumps(snapshot, default=str, indent=2))
    except Exception:
        summary.append("\nDocs/Comms snapshot unavailable (query failed).")

    # Background ingestion of org sources (best-effort)
    try:
        ingest_notes = _run_async(_ingest_external_sources(db, user_id, config or {}))
        if ingest_notes:
            summary.append("\nIngestion:")
            summary.append("\n".join(ingest_notes))
    except Exception as exc:  # noqa: BLE001
        summary.append(f"\nIngestion failed: {exc}")

    return "\n".join(summary)


async def _ingest_external_sources(
    db: Session, user_id: str, config: dict
) -> List[str]:
    """
    Best-effort ingestion of Jira, Confluence, Slack, Teams, Zoom into org memory.
    Configuration is driven by environment variables so background scan can stay automatic.
    """
    notes: List[str] = []

    # Jira
    try:
        jira_keys = await ingest_jira_for_user(db, user_id=user_id, max_issues=25)
        notes.append(f"Jira: {len(jira_keys)} issues synced")
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Jira: skipped/failed ({exc})")

    # Confluence
    space_keys = config.get("confluence_space_keys") or _env_list(
        "AEP_CONFLUENCE_SPACE_KEYS"
    )
    if not space_keys:
        single_space = (
            config.get("confluence_space_key")
            or os.getenv("AEP_CONFLUENCE_SPACE_KEY", "").strip()
        )
        if single_space:
            space_keys = [single_space]
    if space_keys:
        for space in space_keys:
            try:
                page_ids = await ingest_confluence_space(
                    db, user_id=user_id, space_key=space, limit=15
                )
                notes.append(f"Confluence[{space}]: {len(page_ids)} pages")
            except Exception as exc:  # noqa: BLE001
                notes.append(f"Confluence[{space}]: skipped/failed ({exc})")
    else:
        notes.append("Confluence: skipped (no space configured)")

    # Slack
    slack_channels = config.get("slack_channels") or _env_list("AEP_SLACK_CHANNELS")
    if slack_channels:
        try:
            chans = await ingest_slack(
                db, user_id=user_id, channels=slack_channels, limit=120
            )
            notes.append(
                f"Slack: {len(chans)} channels ingested ({', '.join(slack_channels)})"
            )
        except Exception as exc:  # noqa: BLE001
            notes.append(f"Slack: skipped/failed ({exc})")
    else:
        notes.append("Slack: skipped (AEP_SLACK_CHANNELS not set)")

    # Teams
    team_names = config.get("teams") or _env_list("AEP_TEAMS")
    teams_channels = config.get("teams_channels") or _env_list("AEP_TEAMS_CHANNELS")
    if team_names:
        try:
            chan_keys = await ingest_teams(
                db,
                user_id=user_id,
                team_names=team_names,
                channels_per_team=teams_channels or None,
                limit=40,
            )
            notes.append(f"Teams: {len(chan_keys)} channels ({', '.join(team_names)})")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"Teams: skipped/failed ({exc})")
    else:
        notes.append("Teams: skipped (AEP_TEAMS not set)")

    # Zoom
    zoom_user = (
        config.get("zoom_user") or os.getenv("AEP_ZOOM_USER_EMAIL", "")
    ).strip()
    if zoom_user:
        lookback_days = int(
            config.get("zoom_lookback_days")
            or os.getenv("AEP_ZOOM_LOOKBACK_DAYS", "30")
            or "30"
        )
        max_meetings = int(
            config.get("zoom_max_meetings")
            or os.getenv("AEP_ZOOM_MAX_MEETINGS", "20")
            or "20"
        )
        to_date = datetime.now(timezone.utc).date()
        from_date = to_date - timedelta(days=lookback_days)
        try:
            meeting_ids = await ingest_zoom_meetings(
                db,
                user_id=user_id,
                zoom_user=zoom_user,
                from_date=from_date,
                to_date=to_date,
                max_meetings=max_meetings,
            )
            notes.append(f"Zoom: {len(meeting_ids)} meetings ({lookback_days}d window)")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"Zoom: skipped/failed ({exc})")
    else:
        notes.append("Zoom: skipped (AEP_ZOOM_USER_EMAIL not set)")

    return notes
