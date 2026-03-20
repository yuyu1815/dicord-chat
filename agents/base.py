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

    ACTION_PERMISSIONS: dict[str, list[str]] = {}

    async def run(self, state: AgentState, guild: Any) -> AgentState:
        if not state.get("approved"):
            raise PermissionError(f"[{self.name}] Execution requires user approval.")

        user_perms = state.get("user_permissions", {})
        has_admin = user_perms.get("administrator", False)

        denied: list[dict[str, str]] = []

        if not has_admin and self.ACTION_PERMISSIONS:
            todos = state.get("todos", [])
            for todo in todos:
                if todo.get("agent") != self.name:
                    continue
                action = todo.get("action", "")
                required = self.ACTION_PERMISSIONS.get(action, [])
                missing = [p for p in required if not user_perms.get(p, False)]
                if missing:
                    todo["_blocked"] = True
                    denied.append({
                        "action": action,
                        "message": f"このユーザーの権限では実行できません（必要な権限: {', '.join(missing)}）",
                    })

        if "execution_results" not in state:
            state["execution_results"] = {}

        result = await self.execute(state, guild)

        if denied:
            existing = result.get("permission_denied", [])
            result["permission_denied"] = existing + denied

        state["execution_results"][self.name] = result
        return state

    @abstractmethod
    async def execute(self, state: AgentState, guild: Any) -> dict[str, Any]:
        """Perform change operation."""
