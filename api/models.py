"""
Request/Response models for API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

from llm.schemas import ExecutionPlan, FinalOutput


class TaskRequest(BaseModel):
    """Request to submit a new task."""
    task: str = Field(..., min_length=3, max_length=1000, description="Natural language task")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Optional context")
    
    class Config:
        json_schema_extra = {
            "example": {
                "task": "Get the weather in London and find top Python repositories about machine learning"
            }
        }


class TaskResponse(BaseModel):
    """Response from task execution."""
    task_id: str = Field(..., description="Unique task ID")
    status: str = Field(..., description="Task status: success, partial, failed")
    result: Optional[FinalOutput] = Field(default=None, description="Execution result")
    plan: Optional[Dict[str, Any]] = Field(default=None, description="Execution plan")
    execution_time_ms: float = Field(..., description="Total execution time")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    

class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ToolInfo(BaseModel):
    """Information about an available tool."""
    name: str
    description: str
    actions: List[str]
    

class ToolsResponse(BaseModel):
    """Response listing available tools."""
    tools: List[ToolInfo]
    count: int


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    detail: Optional[str] = None
    code: str = "INTERNAL_ERROR"
