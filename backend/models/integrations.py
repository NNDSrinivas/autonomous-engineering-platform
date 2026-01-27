from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, Boolean, ForeignKey, TIMESTAMP, JSON
from ..core.db import Base


# ---- JIRA ----
class JiraConnection(Base):
    __tablename__ = "jira_connection"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    org_id: Mapped[Optional[str]] = mapped_column(String)
    user_id: Mapped[Optional[str]] = mapped_column(String)
    cloud_base_url: Mapped[str] = mapped_column(String)
    token_type: Mapped[Optional[str]] = mapped_column(String)
    access_token: Mapped[Optional[str]] = mapped_column(String)
    refresh_token: Mapped[Optional[str]] = mapped_column(String)
    expires_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    scopes: Mapped[Optional[List[str]]] = mapped_column(JSON)


class JiraProjectConfig(Base):
    __tablename__ = "jira_project_config"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    org_id: Mapped[Optional[str]] = mapped_column(String)
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("jira_connection.id", ondelete="CASCADE")
    )
    project_keys: Mapped[List[str]] = mapped_column(JSON)
    default_jql: Mapped[Optional[str]] = mapped_column(String)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))


class JiraIssue(Base):
    __tablename__ = "jira_issue"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("jira_connection.id", ondelete="CASCADE")
    )
    project_key: Mapped[str] = mapped_column(String)
    issue_key: Mapped[str] = mapped_column(String)
    summary: Mapped[Optional[str]] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[Optional[str]] = mapped_column(String)
    priority: Mapped[Optional[str]] = mapped_column(String)
    assignee: Mapped[Optional[str]] = mapped_column(String)
    reporter: Mapped[Optional[str]] = mapped_column(String)
    labels: Mapped[Optional[List[str]]] = mapped_column(JSON)
    epic_key: Mapped[Optional[str]] = mapped_column(String)
    sprint: Mapped[Optional[str]] = mapped_column(String)
    updated: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    url: Mapped[Optional[str]] = mapped_column(String)
    raw: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    indexed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))


# ---- GitHub ----
class GhConnection(Base):
    __tablename__ = "gh_connection"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    org_id: Mapped[Optional[str]] = mapped_column(String)
    user_id: Mapped[Optional[str]] = mapped_column(String)
    token_type: Mapped[Optional[str]] = mapped_column(String)
    installation_id: Mapped[Optional[str]] = mapped_column(String)
    access_token: Mapped[Optional[str]] = mapped_column(String)
    refresh_token: Mapped[Optional[str]] = mapped_column(String)
    expires_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    scopes: Mapped[Optional[List[str]]] = mapped_column(JSON)


class GhRepo(Base):
    __tablename__ = "gh_repo"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("gh_connection.id", ondelete="CASCADE")
    )
    repo_full_name: Mapped[str] = mapped_column(String)
    default_branch: Mapped[Optional[str]] = mapped_column(String)
    is_private: Mapped[Optional[bool]] = mapped_column(Boolean)
    url: Mapped[Optional[str]] = mapped_column(String)
    last_index_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    index_mode: Mapped[Optional[str]] = mapped_column(String)


class GhFile(Base):
    __tablename__ = "gh_file"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    repo_id: Mapped[str] = mapped_column(ForeignKey("gh_repo.id", ondelete="CASCADE"))
    path: Mapped[str] = mapped_column(String)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    lang: Mapped[Optional[str]] = mapped_column(String)
    sha: Mapped[Optional[str]] = mapped_column(String)
    updated: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))


class GhIssuePr(Base):
    __tablename__ = "gh_issue_pr"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    repo_id: Mapped[str] = mapped_column(ForeignKey("gh_repo.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String)  # issue|pr
    title: Mapped[Optional[str]] = mapped_column(String)
    body: Mapped[Optional[str]] = mapped_column(String)
    state: Mapped[Optional[str]] = mapped_column(String)
    author: Mapped[Optional[str]] = mapped_column(String)
    updated: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    url: Mapped[Optional[str]] = mapped_column(String)
