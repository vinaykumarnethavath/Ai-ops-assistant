"""
FastAPI routes for AI Operations Assistant.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any
import uuid
from datetime import datetime

from .models import (
    TaskRequest, 
    TaskResponse, 
    HealthResponse, 
    ToolsResponse, 
    ToolInfo,
    ErrorResponse
)
from agents.orchestrator import Orchestrator
from agents.base import AgentContext
from tools.registry import get_tool_registry
from utils.cache import get_cache_metrics, clear_cache
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["AI Operations"])


# In-memory task storage (would use Redis/DB in production)
_task_store: Dict[str, TaskResponse] = {}


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse()


@router.get("/tools", response_model=ToolsResponse)
async def list_tools():
    """List all available tools and their actions."""
    registry = get_tool_registry()
    tools = []
    
    for tool in registry.get_all():
        tools.append(ToolInfo(
            name=tool.name,
            description=tool.description,
            actions=[action.name for action in tool.actions]
        ))
    
    return ToolsResponse(tools=tools, count=len(tools))


@router.post("/task", response_model=TaskResponse)
async def submit_task(request: TaskRequest):
    """
    Submit a natural language task for execution.
    
    The task goes through:
    1. Planning - converted to execution steps
    2. Execution - tools are called
    3. Verification - results validated and formatted
    """
    task_id = str(uuid.uuid4())[:8]
    
    logger.info(f"Received task {task_id}: {request.task[:100]}...")
    
    try:
        # Create orchestrator and run
        orchestrator = Orchestrator()
        context = AgentContext(task_id=task_id, original_task=request.task)
        
        result = await orchestrator.run(request.task, context)
        
        # Build response
        response = TaskResponse(
            task_id=task_id,
            status=result.output.status if result.output else "failed",
            result=result.output,
            plan=result.plan.model_dump() if result.plan else None,
            execution_time_ms=result.execution_time_ms
        )
        
        # Store result
        _task_store[task_id] = response
        
        logger.info(f"Task {task_id} completed: {response.status}")
        
        return response
        
    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Task execution failed: {str(e)}"
        )


@router.get("/task/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """Get the result of a previously submitted task."""
    if task_id not in _task_store:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found"
        )
    
    return _task_store[task_id]


@router.get("/cache/stats")
async def cache_stats():
    """Get cache statistics."""
    return get_cache_metrics()


@router.post("/cache/clear")
async def cache_clear():
    """Clear the API response cache."""
    count = clear_cache()
    return {"cleared": count, "message": f"Cleared {count} cached entries"}


@router.get("/agents/status")
async def agents_status():
    """Get status of all agents (useful for debugging)."""
    orchestrator = Orchestrator()
    return orchestrator.get_agent_states()
