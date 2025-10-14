import datetime
import uuid, datetime as dt
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import select, text
from ..models.integrations import JiraConnection, JiraProjectConfig, JiraIssue

def _id(): return str(uuid.uuid4())

def save_connection(db: Session, base_url: str, access_token: str) -> JiraConnection:
    conn = JiraConnection(id=_id(), cloud_base_url=base_url, access_token=access_token, scopes=["read"])
    db.add(conn); db.commit(); db.refresh(conn); return conn

def set_project_config(db: Session, connection_id: str, project_keys: list[str], default_jql: str | None):
    cfg = JiraProjectConfig(id=_id(), connection_id=connection_id, project_keys=project_keys, default_jql=default_jql, last_sync_at=None)
    db.add(cfg); db.commit(); return cfg

def upsert_issue(db: Session, conn_id: str, issue: dict):
    row = db.scalar(select(JiraIssue).where(JiraIssue.issue_key == issue["key"]))
    
    # Handle JIRA description field - could be string or Atlassian Document Format (dict)
    def extract_description_text(desc_field) -> str:
        """Extract plain text from JIRA description field (handles both string and ADF format)"""
        if desc_field is None:
            return ""
        elif isinstance(desc_field, str):
            return desc_field
        elif isinstance(desc_field, dict):
            # Atlassian Document Format - extract text content recursively
            def extract_adf_text(node):
                if isinstance(node, str):
                    return node
                elif isinstance(node, dict):
                    text_parts = []
                    if node.get("type") == "text" and "text" in node:
                        text_parts.append(node["text"])
                    if "content" in node:
                        for child in node["content"]:
                            text_parts.append(extract_adf_text(child))
                    return " ".join(text_parts)
                elif isinstance(node, list):
                    return " ".join(extract_adf_text(item) for item in node)
                return ""
            return extract_adf_text(desc_field).strip()
        else:
            return str(desc_field)
    
    description = extract_description_text(issue["fields"].get("description"))[:8000]
    
    payload = {
        "connection_id": conn_id,
        "project_key": issue["fields"]["project"]["key"],
        "issue_key": issue["key"],
        "summary": issue["fields"].get("summary"),
        "description": description,
        "status": (issue["fields"].get("status") or {}).get("name"),
        "priority": (issue["fields"].get("priority") or {}).get("name"),
        "assignee": ((issue["fields"].get("assignee") or {}).get("displayName")),
        "reporter": ((issue["fields"].get("reporter") or {}).get("displayName")),
        "labels": issue["fields"].get("labels") or [],
        "epic_key": (issue["fields"].get("epic") or {}).get("key"),
        "sprint": None,
        "updated": dt.datetime.fromisoformat(issue["fields"]["updated"].replace("Z","+00:00")) if issue["fields"].get("updated") else None,
        "url": None,
        "raw": issue,
        "indexed_at": dt.datetime.now(datetime.timezone.utc),
    }
    if row:
        for k,v in payload.items(): setattr(row,k,v)
    else:
        row = JiraIssue(id=_id(), **payload)
        db.add(row)
    db.commit()

def search_issues(db: Session, q: str | None, project: str | None, assignee: str | None, updated_since: str | None):
    clause = ["1=1"]; params={}
    if q: clause.append("(summary ILIKE :q OR description ILIKE :q)"); params["q"]=f"%{q}%"
    if project: clause.append("project_key=:p"); params["p"]=project
    if assignee: clause.append("assignee ILIKE :a"); params["a"]=f"%{assignee}%"
    if updated_since: clause.append("updated>=:u"); params["u"]=updated_since
    sql=f"SELECT issue_key as key, summary, status, priority, assignee, updated, url FROM jira_issue WHERE {' AND '.join(clause)} ORDER BY updated DESC NULLS LAST LIMIT 50"
    return [dict(r) for r in db.execute(text(sql), params).mappings().all()]
