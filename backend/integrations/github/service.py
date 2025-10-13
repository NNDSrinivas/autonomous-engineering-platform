"""
GitHub integration service for autonomous engineering platform
Handles repository management, PR automation, and team collaboration
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import httpx
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class PullRequest:
    """Pull request information"""

    number: int
    title: str
    body: str
    state: str
    author: str
    created_at: str
    updated_at: str
    mergeable: bool
    files_changed: int
    additions: int
    deletions: int


@dataclass
class TeamContext:
    """GitHub team context information"""

    active_prs: List[PullRequest]
    recent_commits: List[Dict[str, Any]]
    repository_stats: Dict[str, Any]
    team_activity: Dict[str, Any]


class GitHubService:
    """
    GitHub integration service for engineering teams
    Handles repository operations, PR automation, and team insights
    """

    def __init__(self, token: str, timeout: int = 30):
        self.token = token
        self.timeout = timeout
        self.base_url = "https://api.github.com"

        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Autonomous-Engineering-Platform/1.0",
            },
            timeout=timeout,
        )

        logger.info("GitHub service initialized")

    async def get_team_context(
        self, repositories: Optional[List[str]] = None
    ) -> TeamContext:
        """Get comprehensive team context from GitHub"""

        if not repositories:
            repositories = await self._get_user_repositories()

        # Gather team activity data
        active_prs = []
        recent_commits = []
        repository_stats = {}
        team_activity = {}

        for repo in repositories[:5]:  # Limit to prevent API exhaustion
            try:
                # Get PRs for repo
                prs = await self._get_repository_prs(repo)
                active_prs.extend(prs)

                # Get recent commits
                commits = await self._get_recent_commits(repo)
                recent_commits.extend(commits)

                # Get repository stats
                stats = await self._get_repository_stats(repo)
                repository_stats[repo] = stats

            except Exception as e:
                logger.error(
                    "Error getting context for repository", repo=repo, error=str(e)
                )

        # Analyze team activity patterns
        team_activity = self._analyze_team_activity(active_prs, recent_commits)

        return TeamContext(
            active_prs=active_prs,
            recent_commits=recent_commits,
            repository_stats=repository_stats,
            team_activity=team_activity,
        )

    async def create_pull_request(
        self,
        repository: str,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = "main",
    ) -> Dict[str, Any]:
        """Create a new pull request"""

        url = f"{self.base_url}/repos/{repository}/pulls"

        data = {"title": title, "body": body, "head": head_branch, "base": base_branch}

        try:
            response = await self.client.post(url, json=data)
            response.raise_for_status()

            pr_data = response.json()

            logger.info(
                "Created pull request",
                repository=repository,
                pr_number=pr_data.get("number"),
                title=title,
            )

            return pr_data

        except Exception as e:
            logger.error(
                "Error creating pull request", repository=repository, error=str(e)
            )
            raise

    async def add_pr_comment(
        self, repository: str, pr_number: int, comment: str
    ) -> Dict[str, Any]:
        """Add comment to a pull request"""

        url = f"{self.base_url}/repos/{repository}/issues/{pr_number}/comments"

        data = {"body": comment}

        try:
            response = await self.client.post(url, json=data)
            response.raise_for_status()

            comment_data = response.json()

            logger.info("Added PR comment", repository=repository, pr_number=pr_number)

            return comment_data

        except Exception as e:
            logger.error("Error adding PR comment", repository=repository, error=str(e))
            raise

    async def get_file_content(
        self, repository: str, file_path: str, branch: str = "main"
    ) -> str:
        """Get content of a file from repository"""

        url = f"{self.base_url}/repos/{repository}/contents/{file_path}"
        params = {"ref": branch}

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()

            file_data = response.json()

            # Decode base64 content
            import base64

            content = base64.b64decode(file_data["content"]).decode("utf-8")

            return content

        except Exception as e:
            logger.error(
                "Error getting file content",
                repository=repository,
                file_path=file_path,
                error=str(e),
            )
            raise

    async def create_commit(
        self,
        repository: str,
        file_path: str,
        content: str,
        message: str,
        branch: str = "main",
    ) -> Dict[str, Any]:
        """Create a commit with file changes"""

        # First get the current file SHA if it exists
        try:
            await self.get_file_content(repository, file_path, branch)
            # Get SHA for existing file
            url = f"{self.base_url}/repos/{repository}/contents/{file_path}"
            response = await self.client.get(url, params={"ref": branch})
            current_sha = response.json().get("sha")
        except Exception:
            current_sha = None

        # Create/update file
        url = f"{self.base_url}/repos/{repository}/contents/{file_path}"

        import base64

        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        data = {"message": message, "content": encoded_content, "branch": branch}

        if current_sha:
            data["sha"] = current_sha

        try:
            response = await self.client.put(url, json=data)
            response.raise_for_status()

            commit_data = response.json()

            logger.info(
                "Created commit",
                repository=repository,
                file_path=file_path,
                message=message,
            )

            return commit_data

        except Exception as e:
            logger.error("Error creating commit", repository=repository, error=str(e))
            raise

    async def _get_user_repositories(self) -> List[str]:
        """Get list of user's repositories"""

        url = f"{self.base_url}/user/repos"
        params = {"type": "all", "sort": "updated", "per_page": 20}

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()

            repos = response.json()
            return [repo["full_name"] for repo in repos if not repo.get("archived")]

        except Exception as e:
            logger.error("Error getting user repositories", error=str(e))
            return []

    async def _get_repository_prs(self, repository: str) -> List[PullRequest]:
        """Get pull requests for a repository"""

        url = f"{self.base_url}/repos/{repository}/pulls"
        params = {"state": "open", "sort": "updated", "direction": "desc"}

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()

            prs_data = response.json()

            prs = []
            for pr_data in prs_data:
                pr = PullRequest(
                    number=pr_data["number"],
                    title=pr_data["title"],
                    body=pr_data.get("body", ""),
                    state=pr_data["state"],
                    author=pr_data["user"]["login"],
                    created_at=pr_data["created_at"],
                    updated_at=pr_data["updated_at"],
                    mergeable=pr_data.get("mergeable", False),
                    files_changed=pr_data.get("changed_files", 0),
                    additions=pr_data.get("additions", 0),
                    deletions=pr_data.get("deletions", 0),
                )
                prs.append(pr)

            return prs

        except Exception as e:
            logger.error(
                "Error getting repository PRs", repository=repository, error=str(e)
            )
            return []

    async def _get_recent_commits(self, repository: str) -> List[Dict[str, Any]]:
        """Get recent commits for a repository"""

        url = f"{self.base_url}/repos/{repository}/commits"
        params = {"per_page": 10}

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()

            commits = response.json()

            return [
                {
                    "sha": commit["sha"][:7],
                    "message": commit["commit"]["message"],
                    "author": commit["commit"]["author"]["name"],
                    "date": commit["commit"]["author"]["date"],
                    "repository": repository,
                }
                for commit in commits
            ]

        except Exception as e:
            logger.error(
                "Error getting recent commits", repository=repository, error=str(e)
            )
            return []

    async def _get_repository_stats(self, repository: str) -> Dict[str, Any]:
        """Get statistics for a repository"""

        url = f"{self.base_url}/repos/{repository}"

        try:
            response = await self.client.get(url)
            response.raise_for_status()

            repo_data = response.json()

            return {
                "stars": repo_data.get("stargazers_count", 0),
                "forks": repo_data.get("forks_count", 0),
                "open_issues": repo_data.get("open_issues_count", 0),
                "language": repo_data.get("language", "Unknown"),
                "size": repo_data.get("size", 0),
                "updated_at": repo_data.get("updated_at"),
                "private": repo_data.get("private", False),
            }

        except Exception as e:
            logger.error(
                "Error getting repository stats", repository=repository, error=str(e)
            )
            return {}

    def _analyze_team_activity(
        self, prs: List[PullRequest], commits: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze team activity patterns"""

        # Count PRs by author
        pr_authors = {}
        for pr in prs:
            pr_authors[pr.author] = pr_authors.get(pr.author, 0) + 1

        # Count commits by author
        commit_authors = {}
        for commit in commits:
            author = commit["author"]
            commit_authors[author] = commit_authors.get(author, 0) + 1

        # Calculate team metrics
        total_prs = len(prs)
        total_commits = len(commits)
        active_contributors = len(set(pr_authors.keys()) | set(commit_authors.keys()))

        return {
            "total_open_prs": total_prs,
            "total_recent_commits": total_commits,
            "active_contributors": active_contributors,
            "pr_distribution": pr_authors,
            "commit_distribution": commit_authors,
            "average_pr_size": sum(pr.files_changed for pr in prs) / max(total_prs, 1),
        }

    async def close(self):
        """Cleanup GitHub service resources"""
        await self.client.aclose()
        logger.info("GitHub service cleanup complete")
