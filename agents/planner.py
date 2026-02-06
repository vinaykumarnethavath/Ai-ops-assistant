"""
Planner Agent - Converts natural language tasks into execution plans.
"""

from typing import Any, Optional, List, Dict
import json

from .base import BaseAgent, AgentContext, AgentState
from llm.client import LLMClient
from llm.schemas import ExecutionPlan, PlanStep
from llm.prompts import format_planner_prompt
from tools.registry import get_tool_registry


class PlannerAgent(BaseAgent):
    """
    Planner Agent responsible for:
    1. Understanding the user's natural language task
    2. Breaking it down into discrete steps
    3. Selecting appropriate tools for each step
    4. Defining execution order and dependencies
    """
    
    @property
    def name(self) -> str:
        return "planner"
    
    @property
    def role(self) -> str:
        return "Converts natural language tasks into structured execution plans"
    
    async def run(self, input_data: str, context: AgentContext) -> ExecutionPlan:
        """
        Create an execution plan from a natural language task.
        
        Args:
            input_data: The natural language task description
            context: Execution context
            
        Returns:
            ExecutionPlan with ordered steps and tool selections
        """
        self._set_state(AgentState.THINKING)
        logger = self.get_logger(context.correlation_id)
        
        logger.info(f"Planning task: {input_data[:100]}...", extra={"agent": self.name})
        
        # Get available tools for the prompt
        registry = get_tool_registry()
        tool_schemas = registry.get_all_schemas()
        
        # Build the planning prompt
        prompt = format_planner_prompt(input_data, tool_schemas)
        
        try:
            # Generate structured plan using LLM
            plan = await self.llm.generate_structured(
                prompt=prompt,
                output_schema=ExecutionPlan,
                temperature=0.3  # Lower temperature for more consistent plans
            )
            
            # Validate the plan
            plan = self._validate_plan(plan, registry.get_tool_names())
            
            logger.info(
                f"Created plan with {len(plan.steps)} steps",
                extra={
                    "agent": self.name,
                    "tools_needed": plan.get_tools_needed(),
                    "step_count": len(plan.steps)
                }
            )
            
            self._set_state(AgentState.COMPLETE)
            return plan
            
        except Exception as e:
            logger.error(f"Planning failed: {e}", extra={"agent": self.name})
            self._set_state(AgentState.ERROR)
            
            # Return a minimal fallback plan
            return self._create_fallback_plan(input_data, str(e))
    
    def _validate_plan(self, plan: ExecutionPlan, available_tools: List[str]) -> ExecutionPlan:
        """Validate and clean up the execution plan."""
        valid_steps = []
        
        for step in plan.steps:
            # Check if tool exists
            if step.tool not in available_tools:
                # Try to map common variations
                tool_mapping = {
                    "github_tool": "github",
                    "weather_tool": "weather", 
                    "news_tool": "news",
                    "git": "github",
                    "openweathermap": "weather",
                    "newsapi": "news"
                }
                mapped_tool = tool_mapping.get(step.tool.lower(), step.tool)
                
                if mapped_tool in available_tools:
                    step.tool = mapped_tool
                    valid_steps.append(step)
                # Skip invalid tools
            else:
                valid_steps.append(step)
        
        # Renumber steps
        for i, step in enumerate(valid_steps, 1):
            step.step_number = i
        
        plan.steps = valid_steps
        return plan
    
    def _create_fallback_plan(self, task: str, error: str) -> ExecutionPlan:
        """Create a minimal fallback plan when LLM planning fails."""
        return ExecutionPlan(
            task_understanding=f"Failed to fully understand task: {task[:200]}",
            steps=[],
            expected_output=f"Unable to create plan due to error: {error}"
        )
