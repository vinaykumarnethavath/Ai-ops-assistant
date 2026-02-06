"""
Tool registry for dynamic tool discovery and lookup.
"""

from typing import Dict, List, Any, Optional
from functools import lru_cache

from .base import BaseTool


class ToolRegistry:
    """
    Registry for managing and discovering tools.
    Provides lookup by name and schema generation for LLM.
    """
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool
    
    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def get_all(self) -> List[BaseTool]:
        """Get all registered tools."""
        return list(self._tools.values())
    
    def get_tool_names(self) -> List[str]:
        """Get names of all registered tools."""
        return list(self._tools.keys())
    
    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """Get schemas for all tools (for LLM context)."""
        return [tool.get_schema() for tool in self._tools.values()]
    
    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools
    
    async def execute(self, tool_name: str, action: str, parameters: Dict[str, Any]) -> Any:
        """
        Execute an action on a tool by name.
        
        Args:
            tool_name: Name of the tool
            action: Action to execute
            parameters: Parameters for the action
            
        Returns:
            ToolResult from the execution
            
        Raises:
            KeyError: If tool is not found
        """
        tool = self.get(tool_name)
        if tool is None:
            raise KeyError(f"Tool '{tool_name}' not found. Available: {self.get_tool_names()}")
        
        return await tool.execute(action, parameters)
    
    async def close_all(self) -> None:
        """Close all tool connections."""
        for tool in self._tools.values():
            await tool.close()


# Global registry instance
_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry, creating and populating it if needed."""
    global _registry
    
    if _registry is None:
        _registry = ToolRegistry()
        
        # Import and register all tools
        from .github_tool import GitHubTool
        from .weather_tool import WeatherTool
        from .news_tool import NewsTool
        
        _registry.register(GitHubTool())
        _registry.register(WeatherTool())
        _registry.register(NewsTool())
    
    return _registry


def reset_registry() -> None:
    """Reset the global registry (useful for testing)."""
    global _registry
    if _registry:
        import asyncio
        try:
            asyncio.get_event_loop().run_until_complete(_registry.close_all())
        except:
            pass
    _registry = None
