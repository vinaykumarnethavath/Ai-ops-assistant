"""
Base agent class for AI Operations Assistant.
Provides common functionality for all agents.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import uuid

from llm.client import LLMClient, get_llm_client
from utils.logger import get_context_logger


class AgentState(str, Enum):
    """States an agent can be in."""
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    WAITING = "waiting"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class AgentContext:
    """Context shared between agents during execution."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    original_task: str = ""
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.utcnow)
    
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        return (datetime.utcnow() - self.started_at).total_seconds() * 1000


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    
    Each agent has:
    - A name and role description
    - Access to the LLM client
    - A run method that processes input
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or get_llm_client()
        self.state = AgentState.IDLE
        self._logger = None
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Agent name/identifier."""
        pass
    
    @property
    @abstractmethod
    def role(self) -> str:
        """Description of agent's role."""
        pass
    
    def get_logger(self, correlation_id: Optional[str] = None):
        """Get a logger with agent context."""
        if self._logger is None or correlation_id:
            self._logger = get_context_logger(f"agent.{self.name}", correlation_id)
        return self._logger
    
    @abstractmethod
    async def run(self, input_data: Any, context: AgentContext) -> Any:
        """
        Execute the agent's main logic.
        
        Args:
            input_data: Input specific to the agent type
            context: Shared execution context
            
        Returns:
            Agent-specific output
        """
        pass
    
    def _set_state(self, state: AgentState):
        """Update agent state."""
        self.state = state
        self.get_logger().info(f"State changed to {state.value}", extra={"agent": self.name})
    
    async def think(self, prompt: str, context: AgentContext) -> str:
        """Have the LLM reason about a prompt."""
        self._set_state(AgentState.THINKING)
        logger = self.get_logger(context.correlation_id)
        
        logger.info("Thinking...", extra={"agent": self.name})
        
        try:
            response = await self.llm.generate(prompt)
            return response
        finally:
            self._set_state(AgentState.IDLE)
