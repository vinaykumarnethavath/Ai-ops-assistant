"""
Executor Agent - Executes plan steps and calls APIs.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import asyncio

from .base import BaseAgent, AgentContext, AgentState
from llm.schemas import ExecutionPlan, PlanStep, StepResult, ToolResult
from tools.registry import get_tool_registry
from tools.base import ToolResult as ToolResultData


class ExecutorAgent(BaseAgent):
    """
    Executor Agent responsible for:
    1. Iterating through plan steps
    2. Calling tools with appropriate parameters
    3. Collecting results and handling errors
    4. Tracking partial completion for recovery
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.results: List[StepResult] = []
    
    @property
    def name(self) -> str:
        return "executor"
    
    @property
    def role(self) -> str:
        return "Executes plan steps by calling tools and APIs"
    
    async def run(self, input_data: ExecutionPlan, context: AgentContext) -> List[StepResult]:
        """
        Execute all steps in the plan.
        
        Args:
            input_data: The execution plan from Planner
            context: Execution context
            
        Returns:
            List of StepResult for each executed step
        """
        self._set_state(AgentState.EXECUTING)
        logger = self.get_logger(context.correlation_id)
        
        self.results = []
        registry = get_tool_registry()
        
        logger.info(
            f"Starting execution of {len(input_data.steps)} steps",
            extra={"agent": self.name}
        )
        
        # Build dependency graph
        completed_steps = set()
        
        for step in input_data.steps:
            # Check dependencies
            if not self._dependencies_met(step, completed_steps):
                logger.warning(
                    f"Skipping step {step.step_number}: dependencies not met",
                    extra={"agent": self.name, "step": step.step_number}
                )
                continue
            
            logger.info(
                f"Executing step {step.step_number}: {step.tool}.{step.action}",
                extra={
                    "agent": self.name,
                    "step": step.step_number,
                    "tool": step.tool,
                    "action": step.action
                }
            )
            
            try:
                # Execute the tool action
                tool_result = await registry.execute(
                    tool_name=step.tool,
                    action=step.action,
                    parameters=step.parameters
                )
                
                # Record result
                step_result = StepResult(
                    step_number=step.step_number,
                    tool_result=ToolResult(
                        tool=step.tool,
                        action=step.action,
                        success=tool_result.success,
                        data=tool_result.data,
                        error=tool_result.error,
                        execution_time_ms=tool_result.execution_time_ms,
                        cached=tool_result.cached
                    )
                )
                
                self.results.append(step_result)
                
                if tool_result.success:
                    completed_steps.add(step.step_number)
                    logger.info(
                        f"Step {step.step_number} completed successfully",
                        extra={
                            "agent": self.name,
                            "step": step.step_number,
                            "duration_ms": tool_result.execution_time_ms
                        }
                    )
                else:
                    logger.warning(
                        f"Step {step.step_number} failed: {tool_result.error}",
                        extra={"agent": self.name, "step": step.step_number}
                    )
                    
            except Exception as e:
                logger.error(
                    f"Step {step.step_number} exception: {e}",
                    extra={"agent": self.name, "step": step.step_number}
                )
                
                # Record failed result
                self.results.append(StepResult(
                    step_number=step.step_number,
                    tool_result=ToolResult(
                        tool=step.tool,
                        action=step.action,
                        success=False,
                        error=str(e),
                        execution_time_ms=0
                    )
                ))
        
        self._set_state(AgentState.COMPLETE)
        
        success_count = sum(1 for r in self.results if r.tool_result.success)
        logger.info(
            f"Execution complete: {success_count}/{len(self.results)} steps succeeded",
            extra={"agent": self.name}
        )
        
        return self.results
    
    def _dependencies_met(self, step: PlanStep, completed: set) -> bool:
        """Check if all dependencies for a step are met."""
        if not step.depends_on:
            return True
        return all(dep in completed for dep in step.depends_on)
    
    async def retry_steps(
        self, 
        steps: List[int], 
        plan: ExecutionPlan,
        context: AgentContext
    ) -> List[StepResult]:
        """
        Retry specific steps that failed.
        
        Args:
            steps: Step numbers to retry
            plan: Original execution plan
            context: Execution context
            
        Returns:
            Results of retried steps
        """
        logger = self.get_logger(context.correlation_id)
        retry_results = []
        
        steps_to_retry = [s for s in plan.steps if s.step_number in steps]
        
        for step in steps_to_retry:
            logger.info(f"Retrying step {step.step_number}", extra={"agent": self.name})
            
            registry = get_tool_registry()
            
            try:
                tool_result = await registry.execute(
                    tool_name=step.tool,
                    action=step.action,
                    parameters=step.parameters
                )
                
                step_result = StepResult(
                    step_number=step.step_number,
                    tool_result=ToolResult(
                        tool=step.tool,
                        action=step.action,
                        success=tool_result.success,
                        data=tool_result.data,
                        error=tool_result.error,
                        execution_time_ms=tool_result.execution_time_ms,
                        cached=tool_result.cached
                    )
                )
                retry_results.append(step_result)
                
                # Update original results
                for i, r in enumerate(self.results):
                    if r.step_number == step.step_number:
                        self.results[i] = step_result
                        break
                        
            except Exception as e:
                logger.error(f"Retry of step {step.step_number} failed: {e}")
        
        return retry_results
