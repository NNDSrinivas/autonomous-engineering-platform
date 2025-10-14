from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, Boolean, ForeignKey, TIMESTAMP, JSON
from ..core.db import Base


# ---- JIRA ----
class JiraConnection(Base):
    __tablename__ = "jira_connection"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    org_id: Mapped[str | None] = mapped_column(String)
    user_id: Mapped[str | None] = mapped_column(String)
    cloud_base_url: Mapped[str] = mapped_column(String)
    token_type: Mapped[str | None] = mapped_column(String)
    access_token: Mapped[str | None] = mapped_column(String)
    refresh_token: Mapped[str | None] = mapped_column(String)
    expires_at: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))
    scopes: Mapped[list[str] | None] = mapped_column(JSON)


class JiraProjectConfig(Base):
    __tablename__ = "jira_project_config"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    org_id: Mapped[str | None] = mapped_column(String)
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("jira_connection.id", ondelete="CASCADE")
    )
    project_keys: Mapped[list[str]] = mapped_column(JSON)
    default_jql: Mapped[str | None] = mapped_column(String)
    last_sync_at: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))


class JiraIssue(Base):
    __tablename__ = "jira_issue"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("jira_connection.id", ondelete="CASCADE")
    )
    project_key: Mapped[str] = mapped_column(String)
    issue_key: Mapped[str] = mapped_column(String)
    summary: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String)
    status: Mapped[str | None] = mapped_column(String)
    priority: Mapped[str | None] = mapped_column(String)
    assignee: Mapped[str | None] = mapped_column(String)
    reporter: Mapped[str | None] = mapped_column(String)
    labels: Mapped[list[str] | None] = mapped_column(JSON)
    epic_key: Mapped[str | None] = mapped_column(String)
    sprint: Mapped[str | None] = mapped_column(String)
    updated: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))
    url: Mapped[str | None] = mapped_column(String)
    raw: Mapped[dict | None] = mapped_column(JSON)
    indexed_at: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))


# ---- GitHub ----
class GhConnection(Base):
    __tablename__ = "gh_connection"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    org_id: Mapped[str | None] = mapped_column(String)
    user_id: Mapped[str | None] = mapped_column(String)
    token_type: Mapped[str | None] = mapped_column(String)
    installation_id: Mapped[str | None] = mapped_column(String)
    access_token: Mapped[str | None] = mapped_column(String)
    refresh_token: Mapped[str | None] = mapped_column(String)
    expires_at: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))
    scopes: Mapped[list[str] | None] = mapped_column(JSON)


class GhRepo(Base):
    __tablename__ = "gh_repo"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("gh_connection.id", ondelete="CASCADE")
    )
    repo_full_name: Mapped[str] = mapped_column(String)
    default_branch: Mapped[str | None] = mapped_column(String)
    is_private: Mapped[bool | None] = mapped_column(Boolean)
    url: Mapped[str | None] = mapped_column(String)
    last_index_at: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))
    index_mode: Mapped[str | None] = mapped_column(String)


class GhFile(Base):
    __tablename__ = "gh_file"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    repo_id: Mapped[str] = mapped_column(ForeignKey("gh_repo.id", ondelete="CASCADE"))
    path: Mapped[str] = mapped_column(String)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    lang: Mapped[str | None] = mapped_column(String)
    sha: Mapped[str | None] = mapped_column(String)
    updated: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))


class GhIssuePr(Base):
    __tablename__ = "gh_issue_pr"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    repo_id: Mapped[str] = mapped_column(ForeignKey("gh_repo.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String)  # issue|pr
    title: Mapped[str | None] = mapped_column(String)
    body: Mapped[str | None] = mapped_column(String)
    state: Mapped[str | None] = mapped_column(String)
    author: Mapped[str | None] = mapped_column(String)
    updated: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))
    url: Mapped[str | None] = mapped_column(String)
