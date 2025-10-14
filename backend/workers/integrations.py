import datetime as dt
import dramatiq
import httpx
from dramatiq.brokers.redis import RedisBroker
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..core.config import settings
from ..core.db import SessionLocal
from ..models.integrations import JiraConnection, JiraProjectConfig, GhConnection
from ..services import jira as jsvc, github as ghsvc

broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(broker)


@dramatiq.actor(max_retries=0)
def jira_sync(connection_id: str) -> None:
    db: Session = SessionLocal()
    try:
        conn = db.get(JiraConnection, connection_id)
        cfg = db.scalar(
            select(JiraProjectConfig).where(
                JiraProjectConfig.connection_id == connection_id
            )
        )
        if not conn or not cfg:
            return
        since = (
            cfg.last_sync_at
            or (dt.dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30))
        ).isoformat()
        headers = {
            "Authorization": f"Bearer {conn.access_token}",
            "Accept": "application/json",
        }

        async def fetch():
            async with httpx.AsyncClient(timeout=30) as client:
                for key in cfg.project_keys:
                    start_at = 0
                    while True:
                        jql = f'project={key} AND updated >= "{since}"'
                        r = await client.get(
                            f"{conn.cloud_base_url}/rest/api/3/search",
                            params={"jql": jql, "startAt": start_at, "maxResults": 50},
                            headers=headers,
                        )
                        r.raise_for_status()
                        data = r.json()
                        for issue in data.get("issues", []):
                            jsvc.upsert_issue(db, conn.id, issue)
                        if start_at + 50 >= data.get("total", 0):
                            break
                        start_at += 50

        import anyio

        anyio.run(fetch)
        cfg.last_sync_at = dt.dt.datetime.now(dt.timezone.utc)
        db.commit()
    except Exception:
        pass
    finally:
        db.close()


@dramatiq.actor(max_retries=0)
def github_index(connection_id: str, repo_full_name: str) -> None:
    db: Session = SessionLocal()
    try:
        conn = db.get(GhConnection, connection_id)
        if not conn:
            return
        headers = {
            "Authorization": f"Bearer {conn.access_token}",
            "Accept": "application/vnd.github+json",
        }

        async def fetch():
            async with httpx.AsyncClient(timeout=30) as client:
                # Repo meta
                r = await client.get(
                    f"https://api.github.com/repos/{repo_full_name}", headers=headers
                )
                r.raise_for_status()
                repo = r.json()
                repo_row = ghsvc.upsert_repo(db, conn.id, repo)

                # List files (shallow: use contents API limited)
                tree = await client.get(
                    f"https://api.github.com/repos/{repo_full_name}/git/trees/{repo.get('default_branch')}?recursive=1",
                    headers=headers,
                )
                if tree.status_code == 200:
                    tree_data = tree.json().get("tree", [])
                    # Safely limit the tree data
                    limited_tree = (
                        tree_data[:2000] if isinstance(tree_data, list) else []
                    )
                    for node in limited_tree:
                        if node.get("type") == "blob" and (
                            node.get("path") or ""
                        ).endswith(
                            (
                                ".py",
                                ".js",
                                ".ts",
                                ".java",
                                ".go",
                                ".rb",
                                ".cs",
                                ".kt",
                                ".scala",
                                ".rs",
                                ".sql",
                                ".yaml",
                                ".yml",
                                ".json",
                                ".md",
                            )
                        ):
                            ghsvc.upsert_file(
                                db,
                                repo_row.id,
                                node["path"],
                                node.get("sha"),
                                None,
                                None,
                            )

                # Issues (last 90d)
                r = await client.get(
                    f"https://api.github.com/repos/{repo_full_name}/issues",
                    headers=headers,
                    params={"state": "all", "per_page": 100},
                )
                if r.status_code == 200:
                    for it in r.json():
                        typ = "pr" if "pull_request" in it else "issue"
                        upd = it.get("updated_at")
                        upd = (
                            dt.datetime.fromisoformat(upd.replace("Z", "+00:00"))
                            if upd
                            else None
                        )
                        ghsvc.upsert_issuepr(
                            db,
                            repo_row.id,
                            it["number"],
                            typ,
                            it.get("title", ""),
                            it.get("body", ""),
                            it.get("state", "open"),
                            (it.get("user") or {}).get("login"),
                            it.get("html_url", ""),
                            upd,
                        )

        import anyio

        anyio.run(fetch)
        db.commit()
    except Exception:
        pass
    finally:
        db.close()
