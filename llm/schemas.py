"""
Pydantic schemas for structured LLM outputs.
Defines the data models used across all agents.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict, Literal
from enum import Enum
from datetime import datetime


class ToolName(str, Enum):
    """Available tool names."""
    GITHUB = "github"
    WEATHER = "weather"
    NEWS = "news"


class PlanStep(BaseModel):
    """A single step in the execution plan."""
    step_number: int = Field(..., description="Sequential step number")
    tool: str = Field(..., description="Tool to use for this step")
    action: str = Field(..., description="Specific action/method to call")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Parameters for the action")
    reasoning: str = Field(..., description="Why this step is needed")
    depends_on: List[int] = Field(default_factory=list, description="Step numbers this depends on")


class ExecutionPlan(BaseModel):
    """Complete execution plan from Planner Agent."""
    task_understanding: str = Field(..., description="How the agent understood the task")
    steps: List[PlanStep] = Field(..., description="Ordered list of execution steps")
    expected_output: str = Field(..., description="What the final output should contain")
    
    def get_tools_needed(self) -> List[str]:
        """Get unique list of tools needed for this plan."""
        return list(set(step.tool for step in self.steps))


class ToolResult(BaseModel):
    """Result from a single tool execution."""
    tool: str = Field(..., description="Tool that was executed")
    action: str = Field(..., description="Action that was performed")
    success: bool = Field(..., description="Whether execution succeeded")
    data: Optional[Any] = Field(default=None, description="Returned data")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    execution_time_ms: float = Field(..., description="Execution time in milliseconds")
    cached: bool = Field(default=False, description="Whether result was from cache")


class StepResult(BaseModel):
    """Result of executing a single plan step."""
    step_number: int
    tool_result: ToolResult
    completed_at: datetime = Field(default_factory=datetime.utcnow)


class VerificationStatus(str, Enum):
    """Verification outcome status."""
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class VerificationResult(BaseModel):
    """Result from Verifier Agent validation."""
    status: VerificationStatus = Field(..., description="Overall verification status")
    completeness_score: float = Field(..., ge=0, le=1, description="Score 0-1 for completeness")
    missing_data: List[str] = Field(default_factory=list, description="List of missing data items")
    quality_issues: List[str] = Field(default_factory=list, description="Quality concerns found")
    suggestions: List[str] = Field(default_factory=list, description="Improvement suggestions")
    retry_steps: List[int] = Field(default_factory=list, description="Step numbers to retry")


class FinalOutput(BaseModel):
    """Final structured output to return to user."""
    task: str = Field(..., description="Original task description")
    status: Literal["success", "partial", "failed"] = Field(..., description="Overall status")
    summary: str = Field(..., description="Human-readable summary of results")
    data: Dict[str, Any] = Field(default_factory=dict, description="Structured result data")
    execution_details: Dict[str, Any] = Field(default_factory=dict, description="Execution metadata")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")
    
    class Config:
        json_schema_extra = {
            "example": {
                "task": "Get weather in London",
                "status": "success",
                "summary": "Current weather in London: 15°C, partly cloudy",
                "data": {"temperature": 15, "condition": "partly cloudy"},
                "execution_details": {"steps_completed": 1, "total_time_ms": 250},
                "errors": []
            }
        }


class TaskRequest(BaseModel):
    """Incoming task request from user."""
    task: str = Field(..., min_length=3, description="Natural language task description")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Optional context")
    
    class Config:
        json_schema_extra = {
            "example": {
                "task": "Get the weather in Tokyo and find popular Python repos about AI"
            }
        }


class TaskResponse(BaseModel):
    """Response containing task results."""
    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Task status")
    result: Optional[FinalOutput] = Field(default=None, description="Final result if complete")
    plan: Optional[ExecutionPlan] = Field(default=None, description="Execution plan")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)
