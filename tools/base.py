"""
Base tool interface for AI Operations Assistant.
All tools must inherit from BaseTool and implement the execute method.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import time

from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx


@dataclass
class ToolResult:
    """Result from tool execution."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    cached: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "cached": self.cached
        }


class ToolParameter(BaseModel):
    """Definition of a tool parameter."""
    name: str
    type: str
    description: str
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[List[str]] = None


class ToolAction(BaseModel):
    """Definition of a tool action."""
    name: str
    description: str
    parameters: List[ToolParameter] = []


class BaseTool(ABC):
    """
    Abstract base class for all tools.
    
    Each tool provides:
    - A name and description for LLM tool selection
    - A list of available actions
    - An async execute method
    """
    
    def __init__(self):
        self._http_client: Optional[httpx.AsyncClient] = None
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable tool description."""
        pass
    
    @property
    @abstractmethod
    def actions(self) -> List[ToolAction]:
        """List of available actions for this tool."""
        pass
    
    @abstractmethod
    async def execute(self, action: str, parameters: Dict[str, Any]) -> ToolResult:
        """
        Execute the specified action with given parameters.
        
        Args:
            action: The action name to execute
            parameters: Dictionary of parameters for the action
            
        Returns:
            ToolResult with success status, data, and execution time
        """
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema for LLM context."""
        return {
            "name": self.name,
            "description": self.description,
            "actions": [action.name for action in self.actions],
            "action_details": [action.model_dump() for action in self.actions]
        }
    
    async def get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for API calls."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client
    
    async def close(self):
        """Close HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
    
    def _timed_result(
        self,
        start_time: float,
        success: bool,
        data: Any = None,
        error: str = None,
        cached: bool = False
    ) -> ToolResult:
        """Create a ToolResult with timing information."""
        return ToolResult(
            success=success,
            data=data,
            error=error,
            execution_time_ms=(time.time() - start_time) * 1000,
            cached=cached
        )


def with_retry(max_attempts: int = 3):
    """Decorator to add retry logic to tool methods."""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException))
    )
