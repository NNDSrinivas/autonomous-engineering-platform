import uuid
import datetime as dt
from sqlalchemy.orm import Session
from sqlalchemy import select, text
from ..models.integrations import JiraConnection, JiraProjectConfig, JiraIssue

# Configuration constants
MAX_DESCRIPTION_LENGTH = 8000


class JiraService:
    """JIRA integration service with Atlassian Document Format support"""

    @staticmethod
    def _id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def save_connection(
        db: Session, base_url: str, access_token: str
    ) -> JiraConnection:
        conn = JiraConnection(
            id=JiraService._id(),
            cloud_base_url=base_url,
            access_token=access_token,
            scopes=["read"],
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)
        return conn

    @staticmethod
    def set_project_config(
        db: Session,
        connection_id: str,
        project_keys: list[str],
        default_jql: str | None,
    ):
        cfg = JiraProjectConfig(
            id=JiraService._id(),
            connection_id=connection_id,
            project_keys=project_keys,
            default_jql=default_jql,
            last_sync_at=None,
        )
        db.add(cfg)
        db.commit()
        return cfg

    @staticmethod
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
                # Atlassian Document Format (ADF) - extract text content
                def extract_adf_text(content):
                    if isinstance(content, dict):
                        if content.get("type") == "text":
                            return content.get("text", "")
                        elif "content" in content:
                            return " ".join(
                                extract_adf_text(item) for item in content["content"]
                            )
                    elif isinstance(content, list):
                        return " ".join(extract_adf_text(item) for item in content)
                    return ""

                return extract_adf_text(desc_field)[:MAX_DESCRIPTION_LENGTH]
            else:
                return str(desc_field)[:MAX_DESCRIPTION_LENGTH]

        description = extract_description_text(
            issue.get("fields", {}).get("description")
        )

        payload = {
            "connection_id": conn_id,
            "issue_key": issue["key"],
            "project_key": issue["fields"]["project"]["key"],
            "issue_type": issue["fields"]["issuetype"]["name"],
            "summary": issue["fields"]["summary"],
            "description": description,
            "status": issue["fields"]["status"]["name"],
            "assignee": (
                issue["fields"]["assignee"]["displayName"]
                if issue["fields"]["assignee"]
                else None
            ),
            "reporter": (
                issue["fields"]["reporter"]["displayName"]
                if issue["fields"]["reporter"]
                else None
            ),
            "priority": (
                issue["fields"]["priority"]["name"]
                if issue["fields"]["priority"]
                else None
            ),
            "created": dt.datetime.fromisoformat(
                issue["fields"]["created"].replace("Z", "+00:00")
            ),
            "updated": dt.datetime.fromisoformat(
                issue["fields"]["updated"].replace("Z", "+00:00")
            ),
            "url": f"{issue['self'].split('/rest/')[0]}/browse/{issue['key']}",
        }

        if row:
            for k, v in payload.items():
                setattr(row, k, v)
        else:
            row = JiraIssue(id=JiraService._id(), **payload)
            db.add(row)
        db.commit()
        return row

    @staticmethod
    def search_issues(
        db: Session, project: str | None, q: str | None, updated_since: str | None
    ):
        clause = ["1=1"]
        params = {}
        if project:
            clause.append("project_key=:proj")
            params["proj"] = project
        if updated_since:
            clause.append("updated>=:u")
            params["u"] = updated_since
        if q:
            clause.append("(summary ILIKE :q OR description ILIKE :q)")
            params["q"] = f"%{q}%"
        sql = f"SELECT issue_key, project_key, issue_type, summary, status, assignee, updated, url FROM jira_issue WHERE {' AND '.join(clause)} ORDER BY updated DESC NULLS LAST LIMIT 50"
        return [dict(r) for r in db.execute(text(sql), params).mappings().all()]
