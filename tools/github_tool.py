"""
GitHub API Tool for AI Operations Assistant.
Provides repository search, details, and user information.
"""

import time
from typing import Any, Dict, List, Optional

from .base import BaseTool, ToolResult, ToolAction, ToolParameter, with_retry
from config import get_settings
from utils.cache import cached_api_call
from utils.logger import get_logger

logger = get_logger(__name__)


class GitHubTool(BaseTool):
    """Tool for interacting with GitHub API."""
    
    BASE_URL = "https://api.github.com"
    
    @property
    def name(self) -> str:
        return "github"
    
    @property
    def description(self) -> str:
        return "Search GitHub repositories, get repository details, and fetch user information"
    
    @property
    def actions(self) -> List[ToolAction]:
        return [
            ToolAction(
                name="search_repositories",
                description="Search for GitHub repositories by query",
                parameters=[
                    ToolParameter(name="query", type="string", description="Search query (e.g., 'machine learning', 'language:python')"),
                    ToolParameter(name="sort", type="string", description="Sort by: stars, forks, updated", required=False, default="stars", enum=["stars", "forks", "updated"]),
                    ToolParameter(name="limit", type="integer", description="Max results (1-30)", required=False, default=5),
                ]
            ),
            ToolAction(
                name="get_repository",
                description="Get detailed information about a specific repository",
                parameters=[
                    ToolParameter(name="owner", type="string", description="Repository owner username"),
                    ToolParameter(name="repo", type="string", description="Repository name"),
                ]
            ),
            ToolAction(
                name="get_user",
                description="Get GitHub user profile information",
                parameters=[
                    ToolParameter(name="username", type="string", description="GitHub username"),
                ]
            ),
        ]
    
    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AI-Ops-Assistant"
        }
        settings = get_settings()
        if settings.github_token:
            headers["Authorization"] = f"token {settings.github_token}"
        return headers
    
    async def execute(self, action: str, parameters: Dict[str, Any]) -> ToolResult:
        """Execute a GitHub API action."""
        start_time = time.time()
        
        try:
            if action == "search_repositories":
                return await self._search_repositories(start_time, **parameters)
            elif action == "get_repository":
                return await self._get_repository(start_time, **parameters)
            elif action == "get_user":
                return await self._get_user(start_time, **parameters)
            else:
                return self._timed_result(
                    start_time, False, 
                    error=f"Unknown action: {action}. Available: {[a.name for a in self.actions]}"
                )
        except Exception as e:
            logger.error(f"GitHub API error: {e}", extra={"action": action})
            return self._timed_result(start_time, False, error=str(e))
    
    @cached_api_call(ttl_seconds=300)
    async def _search_repositories(
        self, 
        start_time: float,
        query: str, 
        sort: str = "stars",
        limit: int = 5
    ) -> ToolResult:
        """Search GitHub repositories."""
        client = await self.get_http_client()
        
        url = f"{self.BASE_URL}/search/repositories"
        params = {
            "q": query,
            "sort": sort,
            "order": "desc",
            "per_page": min(limit, 30)
        }
        
        response = await client.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        
        data = response.json()
        
        # Extract relevant fields
        repos = []
        for item in data.get("items", [])[:limit]:
            repos.append({
                "name": item["full_name"],
                "description": item.get("description", "No description"),
                "stars": item["stargazers_count"],
                "forks": item["forks_count"],
                "language": item.get("language", "Unknown"),
                "url": item["html_url"],
                "updated_at": item["updated_at"]
            })
        
        logger.info(f"Found {len(repos)} repositories for query: {query}")
        
        return self._timed_result(start_time, True, data={
            "query": query,
            "total_count": data.get("total_count", 0),
            "repositories": repos
        })
    
    @cached_api_call(ttl_seconds=300)
    async def _get_repository(
        self,
        start_time: float, 
        owner: str, 
        repo: str
    ) -> ToolResult:
        """Get repository details."""
        client = await self.get_http_client()
        
        url = f"{self.BASE_URL}/repos/{owner}/{repo}"
        response = await client.get(url, headers=self._get_headers())
        response.raise_for_status()
        
        data = response.json()
        
        result = {
            "name": data["full_name"],
            "description": data.get("description", "No description"),
            "stars": data["stargazers_count"],
            "forks": data["forks_count"],
            "watchers": data["watchers_count"],
            "language": data.get("language", "Unknown"),
            "topics": data.get("topics", []),
            "created_at": data["created_at"],
            "updated_at": data["updated_at"],
            "open_issues": data["open_issues_count"],
            "license": data.get("license", {}).get("name", "None"),
            "url": data["html_url"]
        }
        
        return self._timed_result(start_time, True, data=result)
    
    @cached_api_call(ttl_seconds=300)
    async def _get_user(self, start_time: float, username: str) -> ToolResult:
        """Get user profile."""
        client = await self.get_http_client()
        
        url = f"{self.BASE_URL}/users/{username}"
        response = await client.get(url, headers=self._get_headers())
        response.raise_for_status()
        
        data = response.json()
        
        result = {
            "username": data["login"],
            "name": data.get("name", "Unknown"),
            "bio": data.get("bio", ""),
            "company": data.get("company", ""),
            "location": data.get("location", ""),
            "public_repos": data["public_repos"],
            "followers": data["followers"],
            "following": data["following"],
            "created_at": data["created_at"],
            "profile_url": data["html_url"]
        }
        
        return self._timed_result(start_time, True, data=result)
