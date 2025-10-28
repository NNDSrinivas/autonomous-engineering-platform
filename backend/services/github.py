import uuid
import datetime as dt
from sqlalchemy.orm import Session
from sqlalchemy import select, text
from ..models.integrations import GhConnection, GhRepo, GhFile, GhIssuePr
from ..core.crypto import encrypt_token

# Configuration constants
MAX_BODY_LENGTH = 8000


class GitHubService:
    """GitHub integration service for repository indexing and issue tracking"""

    @staticmethod
    def _id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def save_connection(db: Session, access_token: str) -> GhConnection:
        conn = GhConnection(
            id=GitHubService._id(),
            access_token=encrypt_token(access_token),
            scopes=["repo", "read:org"],
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)
        return conn

    @staticmethod
    def upsert_repo(db: Session, conn_id: str, repo: dict):
        row = db.scalar(select(GhRepo).where(GhRepo.repo_full_name == repo["full_name"]))
        payload = {
            "connection_id": conn_id,
            "repo_full_name": repo["full_name"],
            "default_branch": repo.get("default_branch"),
            "is_private": repo.get("private"),
            "url": repo.get("html_url"),
            "last_index_at": None,
            "index_mode": "api",
        }
        if row:
            for k, v in payload.items():
                setattr(row, k, v)
        else:
            row = GhRepo(id=GitHubService._id(), **payload)
            db.add(row)
        db.commit()
        return row

    @staticmethod
    def upsert_file(
        db: Session,
        repo_id: str,
        path: str,
        sha: str | None,
        lang: str | None,
        size: int | None,
    ):
        row = GhFile(
            id=GitHubService._id(),
            repo_id=repo_id,
            path=path,
            sha=sha,
            lang=lang,
            size_bytes=size,
            updated=dt.datetime.now(dt.timezone.utc),
        )
        db.add(row)
        db.commit()

    @staticmethod
    def upsert_issuepr(
        db: Session,
        repo_id: str,
        number: int,
        type_: str,
        title: str,
        body: str | None,
        state: str,
        author: str | None,
        url: str,
        updated: dt.datetime | None,
    ):
        # Safely handle body field - ensure it's a string before slicing
        safe_body = ""
        if body is not None:
            if isinstance(body, str):
                safe_body = body[:MAX_BODY_LENGTH]
            else:
                safe_body = str(body)[:MAX_BODY_LENGTH]

        row = GhIssuePr(
            id=GitHubService._id(),
            repo_id=repo_id,
            number=number,
            type=type_,
            title=title,
            body=safe_body,
            state=state,
            author=author,
            url=url,
            updated=updated,
        )
        db.add(row)
        db.commit()

    @staticmethod
    def search_code(db: Session, repo: str | None, q: str | None, path_prefix: str | None):
        clause = ["1=1"]
        params = {}
        join = "JOIN gh_repo r ON r.id=f.repo_id"
        if repo:
            clause.append("r.repo_full_name=:repo")
            params["repo"] = repo
        if path_prefix:
            clause.append("f.path LIKE :pp")
            params["pp"] = f"{path_prefix}%"
        sql = f"SELECT r.repo_full_name as repo, f.path, f.lang, f.sha, f.updated FROM gh_file f {join} WHERE {' AND '.join(clause)} ORDER BY f.updated DESC NULLS LAST LIMIT 50"
        return [dict(r) for r in db.execute(text(sql), params).mappings().all()]

    @staticmethod
    def search_issues(db: Session, repo: str | None, q: str | None, updated_since: str | None):
        clause = ["1=1"]
        params = {}
        join = "JOIN gh_repo r ON r.id=ip.repo_id"
        if repo:
            clause.append("r.repo_full_name=:repo")
            params["repo"] = repo
        if updated_since:
            clause.append("ip.updated>=:u")
            params["u"] = updated_since
        if q:
            clause.append("(ip.title ILIKE :q OR ip.body ILIKE :q)")
            params["q"] = f"%{q}%"
        sql = f"SELECT r.repo_full_name as repo, ip.number, ip.type, ip.title, ip.state, ip.updated, ip.url FROM gh_issue_pr ip {join} WHERE {' AND '.join(clause)} ORDER BY ip.updated DESC NULLS LAST LIMIT 50"
        return [dict(r) for r in db.execute(text(sql), params).mappings().all()]
