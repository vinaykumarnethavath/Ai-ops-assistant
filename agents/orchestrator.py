"""
Orchestrator - Coordinates the multi-agent workflow.
Implements a state machine: PLANNING → EXECUTING → VERIFYING → COMPLETE
"""

from typing import Any, Dict, Optional
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

from .base import AgentContext
from .planner import PlannerAgent
from .executor import ExecutorAgent
from .verifier import VerifierAgent
from llm.schemas import ExecutionPlan, FinalOutput, StepResult
from llm.client import LLMClient, get_llm_client
from utils.logger import get_context_logger


class OrchestratorState(str, Enum):
    """States for the orchestration workflow."""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    RETRYING = "retrying"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class OrchestratorResult:
    """Complete result from orchestrator execution."""
    state: OrchestratorState
    output: Optional[FinalOutput] = None
    plan: Optional[ExecutionPlan] = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0


class Orchestrator:
    """
    Main orchestrator that coordinates Planner, Executor, and Verifier agents.
    
    Workflow:
    1. PLANNING: Planner converts task to execution plan
    2. EXECUTING: Executor runs through plan steps
    3. VERIFYING: Verifier validates and formats output
    4. RETRYING: (if needed) Re-execute failed steps
    5. COMPLETE: Return final result
    """
    
    def __init__(
        self, 
        llm_client: Optional[LLMClient] = None,
        max_retries: int = 2
    ):
        self.llm = llm_client or get_llm_client()
        self.max_retries = max_retries
        
        # Initialize agents
        self.planner = PlannerAgent(self.llm)
        self.executor = ExecutorAgent(self.llm)
        self.verifier = VerifierAgent(self.llm)
        
        self.state = OrchestratorState.IDLE
        self._logger = None
    
    def get_logger(self, correlation_id: Optional[str] = None):
        """Get logger with context."""
        if self._logger is None or correlation_id:
            self._logger = get_context_logger("orchestrator", correlation_id)
        return self._logger
    
    async def run(self, task: str, context: Optional[AgentContext] = None) -> OrchestratorResult:
        """
        Execute the full orchestration workflow.
        
        Args:
            task: Natural language task from user
            context: Optional execution context
            
        Returns:
            OrchestratorResult with final output
        """
        start_time = datetime.utcnow()
        
        # Create context if not provided
        if context is None:
            context = AgentContext(original_task=task)
        else:
            context.original_task = task
        
        logger = self.get_logger(context.correlation_id)
        logger.info(f"Starting orchestration for task: {task[:100]}...")
        
        try:
            # Phase 1: Planning
            self.state = OrchestratorState.PLANNING
            logger.info("Phase 1: Planning", extra={"state": self.state.value})
            
            plan = await self.planner.run(task, context)
            
            if not plan.steps:
                logger.warning("Planner returned empty plan")
                return OrchestratorResult(
                    state=OrchestratorState.ERROR,
                    plan=plan,
                    error="Could not create an execution plan for this task",
                    execution_time_ms=self._elapsed_ms(start_time)
                )
            
            # Phase 2: Execution
            self.state = OrchestratorState.EXECUTING
            logger.info(
                f"Phase 2: Executing {len(plan.steps)} steps",
                extra={"state": self.state.value}
            )
            
            results = await self.executor.run(plan, context)
            
            # Phase 3: Verification
            self.state = OrchestratorState.VERIFYING
            logger.info("Phase 3: Verifying", extra={"state": self.state.value})
            
            output = await self.verifier.run({
                "plan": plan,
                "results": results,
                "task": task
            }, context)
            
            # Phase 4: Retry if needed
            if output.status == "partial" and self.max_retries > 0:
                output = await self._handle_retries(
                    plan, results, output, task, context, logger
                )
            
            # Complete
            self.state = OrchestratorState.COMPLETE
            execution_time = self._elapsed_ms(start_time)
            
            logger.info(
                f"Orchestration complete: {output.status}",
                extra={
                    "state": self.state.value,
                    "duration_ms": execution_time,
                    "status": output.status
                }
            )
            
            return OrchestratorResult(
                state=self.state,
                output=output,
                plan=plan,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            self.state = OrchestratorState.ERROR
            logger.error(f"Orchestration failed: {e}")
            
            return OrchestratorResult(
                state=self.state,
                error=str(e),
                execution_time_ms=self._elapsed_ms(start_time)
            )
    
    async def _handle_retries(
        self,
        plan: ExecutionPlan,
        results: list,
        output: FinalOutput,
        task: str,
        context: AgentContext,
        logger
    ) -> FinalOutput:
        """Handle retries for failed steps."""
        retry_count = 0
        
        while output.status == "partial" and retry_count < self.max_retries:
            retry_count += 1
            self.state = OrchestratorState.RETRYING
            
            # Find steps to retry from errors
            failed_steps = [
                i + 1 for i, r in enumerate(results) 
                if not r.tool_result.success
            ]
            
            if not failed_steps:
                break
            
            logger.info(
                f"Retry attempt {retry_count}: retrying steps {failed_steps[:3]}",
                extra={"state": self.state.value}
            )
            
            # Retry failed steps
            retry_results = await self.executor.retry_steps(
                failed_steps[:3],  # Limit retries
                plan,
                context
            )
            
            # Re-verify
            self.state = OrchestratorState.VERIFYING
            output = await self.verifier.run({
                "plan": plan,
                "results": self.executor.results,
                "task": task
            }, context)
        
        return output
    
    def _elapsed_ms(self, start_time: datetime) -> float:
        """Calculate elapsed milliseconds."""
        return (datetime.utcnow() - start_time).total_seconds() * 1000
    
    def get_state(self) -> OrchestratorState:
        """Get current orchestrator state."""
        return self.state
    
    def get_agent_states(self) -> Dict[str, str]:
        """Get states of all agents."""
        return {
            "orchestrator": self.state.value,
            "planner": self.planner.state.value,
            "executor": self.executor.state.value,
            "verifier": self.verifier.state.value
        }
