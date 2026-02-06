"""
NewsAPI Tool for AI Operations Assistant.
Provides news headlines and article search across multiple sources.
"""

import time
from typing import Any, Dict, List

from .base import BaseTool, ToolResult, ToolAction, ToolParameter
from config import get_settings
from utils.cache import cached_api_call
from utils.logger import get_logger

logger = get_logger(__name__)


class NewsTool(BaseTool):
    """Tool for fetching news from NewsAPI."""
    
    BASE_URL = "https://newsapi.org/v2"
    
    @property
    def name(self) -> str:
        return "news"
    
    @property
    def description(self) -> str:
        return "Get top news headlines and search for articles on specific topics"
    
    @property
    def actions(self) -> List[ToolAction]:
        return [
            ToolAction(
                name="get_top_headlines",
                description="Get top news headlines, optionally filtered by category or country",
                parameters=[
                    ToolParameter(name="category", type="string", description="News category", required=False, 
                                 enum=["business", "entertainment", "general", "health", "science", "sports", "technology"]),
                    ToolParameter(name="country", type="string", description="2-letter country code (e.g., 'us', 'gb', 'in')", required=False, default="us"),
                    ToolParameter(name="limit", type="integer", description="Max articles (1-20)", required=False, default=5),
                ]
            ),
            ToolAction(
                name="search_news",
                description="Search for news articles by keyword or phrase",
                parameters=[
                    ToolParameter(name="query", type="string", description="Search query (keywords or phrases)"),
                    ToolParameter(name="sort_by", type="string", description="Sort order", required=False, default="publishedAt",
                                 enum=["relevancy", "popularity", "publishedAt"]),
                    ToolParameter(name="limit", type="integer", description="Max articles (1-20)", required=False, default=5),
                ]
            ),
        ]
    
    async def execute(self, action: str, parameters: Dict[str, Any]) -> ToolResult:
        """Execute a news API action."""
        start_time = time.time()
        
        try:
            if action == "get_top_headlines":
                return await self._get_top_headlines(start_time, **parameters)
            elif action == "search_news":
                return await self._search_news(start_time, **parameters)
            else:
                return self._timed_result(
                    start_time, False,
                    error=f"Unknown action: {action}. Available: {[a.name for a in self.actions]}"
                )
        except Exception as e:
            logger.error(f"News API error: {e}", extra={"action": action})
            return self._timed_result(start_time, False, error=str(e))
    
    def _format_article(self, article: Dict) -> Dict[str, Any]:
        """Format an article for output."""
        return {
            "title": article.get("title", "Untitled"),
            "description": article.get("description", "No description"),
            "source": article.get("source", {}).get("name", "Unknown"),
            "author": article.get("author", "Unknown"),
            "url": article.get("url", ""),
            "published_at": article.get("publishedAt", ""),
            "image_url": article.get("urlToImage", "")
        }
    
    @cached_api_call(ttl_seconds=900)  # Cache news for 15 minutes
    async def _get_top_headlines(
        self,
        start_time: float,
        category: str = None,
        country: str = "us",
        limit: int = 5
    ) -> ToolResult:
        """Get top headlines."""
        settings = get_settings()
        client = await self.get_http_client()
        
        url = f"{self.BASE_URL}/top-headlines"
        params = {
            "apiKey": settings.newsapi_key,
            "country": country,
            "pageSize": min(limit, 20)
        }
        
        if category:
            params["category"] = category
        
        response = await client.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("status") != "ok":
            return self._timed_result(
                start_time, False, 
                error=data.get("message", "Unknown NewsAPI error")
            )
        
        articles = [self._format_article(a) for a in data.get("articles", [])[:limit]]
        
        result = {
            "category": category or "general",
            "country": country,
            "total_results": data.get("totalResults", 0),
            "articles": articles
        }
        
        logger.info(f"Retrieved {len(articles)} headlines for {category or 'general'} in {country}")
        
        return self._timed_result(start_time, True, data=result)
    
    @cached_api_call(ttl_seconds=900)
    async def _search_news(
        self,
        start_time: float,
        query: str,
        sort_by: str = "publishedAt",
        limit: int = 5
    ) -> ToolResult:
        """Search for news articles."""
        settings = get_settings()
        client = await self.get_http_client()
        
        url = f"{self.BASE_URL}/everything"
        params = {
            "apiKey": settings.newsapi_key,
            "q": query,
            "sortBy": sort_by,
            "pageSize": min(limit, 20),
            "language": "en"
        }
        
        response = await client.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("status") != "ok":
            return self._timed_result(
                start_time, False,
                error=data.get("message", "Unknown NewsAPI error")
            )
        
        articles = [self._format_article(a) for a in data.get("articles", [])[:limit]]
        
        result = {
            "query": query,
            "sort_by": sort_by,
            "total_results": data.get("totalResults", 0),
            "articles": articles
        }
        
        logger.info(f"Found {len(articles)} articles for query: {query}")
        
        return self._timed_result(start_time, True, data=result)
