"""
Verifier Agent - Validates results and formats final output.
"""

from typing import Any, Dict, List, Optional
import json

from .base import BaseAgent, AgentContext, AgentState
from llm.schemas import (
    ExecutionPlan, 
    StepResult, 
    VerificationResult, 
    VerificationStatus,
    FinalOutput
)
from llm.prompts import format_verifier_prompt


class VerifierAgent(BaseAgent):
    """
    Verifier Agent responsible for:
    1. Validating completeness of execution results
    2. Checking data quality and consistency
    3. Identifying missing information
    4. Formatting final structured output
    """
    
    @property
    def name(self) -> str:
        return "verifier"
    
    @property
    def role(self) -> str:
        return "Validates results and produces final structured output"
    
    async def run(
        self, 
        input_data: Dict[str, Any], 
        context: AgentContext
    ) -> FinalOutput:
        """
        Verify execution results and produce final output.
        
        Args:
            input_data: Dict with 'plan', 'results', and 'task' keys
            context: Execution context
            
        Returns:
            FinalOutput with formatted results
        """
        self._set_state(AgentState.THINKING)
        logger = self.get_logger(context.correlation_id)
        
        plan: ExecutionPlan = input_data["plan"]
        results: List[StepResult] = input_data["results"]
        original_task: str = input_data["task"]
        
        logger.info("Verifying execution results", extra={"agent": self.name})
        
        # Analyze results
        verification = await self._verify_results(original_task, results, context)
        
        logger.info(
            f"Verification complete: {verification.status.value}, "
            f"completeness: {verification.completeness_score:.0%}",
            extra={"agent": self.name}
        )
        
        # Format final output
        final_output = await self._format_output(
            original_task, 
            plan, 
            results, 
            verification,
            context
        )
        
        self._set_state(AgentState.COMPLETE)
        return final_output
    
    async def _verify_results(
        self, 
        task: str, 
        results: List[StepResult],
        context: AgentContext
    ) -> VerificationResult:
        """Verify the execution results."""
        logger = self.get_logger(context.correlation_id)
        
        # Calculate basic metrics
        total_steps = len(results)
        successful_steps = sum(1 for r in results if r.tool_result.success)
        
        if total_steps == 0:
            return VerificationResult(
                status=VerificationStatus.FAILED,
                completeness_score=0.0,
                missing_data=["No steps were executed"],
                quality_issues=["Empty execution results"],
                suggestions=["Verify the task can be understood and appropriate tools are available"]
            )
        
        completeness = successful_steps / total_steps
        
        # Identify missing data and issues
        missing_data = []
        quality_issues = []
        retry_steps = []
        
        for result in results:
            if not result.tool_result.success:
                missing_data.append(
                    f"Step {result.step_number} ({result.tool_result.tool}.{result.tool_result.action}) failed: "
                    f"{result.tool_result.error}"
                )
                retry_steps.append(result.step_number)
            elif result.tool_result.data is None:
                quality_issues.append(
                    f"Step {result.step_number} returned empty data"
                )
        
        # Determine status
        if completeness >= 0.9:
            status = VerificationStatus.COMPLETE
        elif completeness >= 0.5:
            status = VerificationStatus.PARTIAL
        else:
            status = VerificationStatus.FAILED
        
        # Generate suggestions
        suggestions = []
        if retry_steps:
            suggestions.append(f"Consider retrying failed steps: {retry_steps}")
        if completeness < 1.0:
            suggestions.append("Some data may be incomplete - results are partial")
        
        return VerificationResult(
            status=status,
            completeness_score=completeness,
            missing_data=missing_data[:5],  # Limit to 5
            quality_issues=quality_issues[:5],
            suggestions=suggestions[:3],
            retry_steps=retry_steps[:3]  # Only retry up to 3 steps
        )
    
    async def _format_output(
        self,
        task: str,
        plan: ExecutionPlan,
        results: List[StepResult],
        verification: VerificationResult,
        context: AgentContext
    ) -> FinalOutput:
        """Format the final output for the user."""
        logger = self.get_logger(context.correlation_id)
        
        # Determine overall status
        if verification.status == VerificationStatus.COMPLETE:
            status = "success"
        elif verification.status == VerificationStatus.PARTIAL:
            status = "partial"
        else:
            status = "failed"
        
        # Collect data from successful steps
        collected_data = {}
        for result in results:
            if result.tool_result.success and result.tool_result.data:
                tool_key = f"{result.tool_result.tool}_{result.tool_result.action}"
                collected_data[tool_key] = result.tool_result.data
        
        # Generate summary using LLM
        try:
            summary = await self._generate_summary(task, collected_data, context)
        except Exception as e:
            logger.warning(f"Failed to generate LLM summary: {e}")
            summary = self._create_fallback_summary(task, collected_data, verification)
        
        # Collect errors
        errors = [
            f"{r.tool_result.tool}: {r.tool_result.error}"
            for r in results 
            if not r.tool_result.success and r.tool_result.error
        ]
        
        # Execution details
        total_time_ms = sum(r.tool_result.execution_time_ms for r in results)
        execution_details = {
            "steps_total": len(results),
            "steps_succeeded": sum(1 for r in results if r.tool_result.success),
            "steps_failed": sum(1 for r in results if not r.tool_result.success),
            "total_time_ms": round(total_time_ms, 2),
            "cached_results": sum(1 for r in results if r.tool_result.cached),
            "completeness_score": verification.completeness_score,
            "task_id": context.task_id
        }
        
        return FinalOutput(
            task=task,
            status=status,
            summary=summary,
            data=collected_data,
            execution_details=execution_details,
            errors=errors
        )
    
    async def _generate_summary(
        self, 
        task: str, 
        data: Dict[str, Any],
        context: AgentContext
    ) -> str:
        """Generate a human-readable summary using LLM."""
        prompt = f"""Summarize the following results for the task: "{task}"

Results:
{json.dumps(data, indent=2, default=str)[:3000]}

Provide a clear, concise 2-3 sentence summary of what was found. Focus on the key information the user asked for."""

        response = await self.llm.generate(prompt, temperature=0.5)
        return response.strip()
    
    def _create_fallback_summary(
        self, 
        task: str, 
        data: Dict[str, Any],
        verification: VerificationResult
    ) -> str:
        """Create a basic summary when LLM fails."""
        parts = [f"Task: {task}"]
        
        if verification.status == VerificationStatus.COMPLETE:
            parts.append(f"Successfully retrieved all requested information.")
        elif verification.status == VerificationStatus.PARTIAL:
            parts.append(f"Partially completed. Some information could not be retrieved.")
        else:
            parts.append(f"Failed to complete the task.")
        
        # Add data highlights
        for key, value in list(data.items())[:3]:
            if isinstance(value, dict):
                if "city" in value:
                    parts.append(f"Weather for {value.get('city')}: {value.get('temperature')}°")
                elif "repositories" in value:
                    parts.append(f"Found {len(value['repositories'])} repositories")
                elif "articles" in value:
                    parts.append(f"Found {len(value['articles'])} news articles")
        
        return " ".join(parts)
