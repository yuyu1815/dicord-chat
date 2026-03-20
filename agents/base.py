from abc import ABC, abstractmethod
from typing import Any

from graph.state import AgentState


class BaseAgent(ABC):
    """All agents inherit from this."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique agent identifier."""

    @abstractmethod
    async def run(self, state: AgentState, guild: Any) -> AgentState:
        """Execute agent logic, return updated state."""


class InvestigationAgent(BaseAgent):
    """Read-only agent that gathers information."""

    async def run(self, state: AgentState, guild: Any) -> AgentState:
        if "investigation_results" not in state:
            state["investigation_results"] = {}
        result = await self.investigate(state, guild)
        state["investigation_results"][self.name] = result
        return state

    @abstractmethod
    async def investigate(self, state: AgentState, guild: Any) -> dict[str, Any]:
        """Gather information (read-only)."""


class ExecutionAgent(BaseAgent):
    """Write agent that performs changes after user approval."""

    async def run(self, state: AgentState, guild: Any) -> AgentState:
        if not state.get("approved"):
            raise PermissionError(f"[{self.name}] Execution requires user approval.")
        if "execution_results" not in state:
            state["execution_results"] = {}
        result = await self.execute(state, guild)
        state["execution_results"][self.name] = result
        return state

    @abstractmethod
    async def execute(self, state: AgentState, guild: Any) -> dict[str, Any]:
        """Perform change operation."""
