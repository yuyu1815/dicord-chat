from abc import ABC, abstractmethod
from typing import Any

from graph.state import AgentState


class BaseAgent(ABC):
    """全エージェントの基底クラス。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """エージェントの一意識別子を返す。"""

    @abstractmethod
    async def run(self, state: AgentState, guild: Any) -> AgentState:
        """エージェントの処理を実行し、更新済みの状態を返す。

        Args:
            state: LangGraphワークフローの状態。
            guild: 対象のDiscordサーバー。

        Returns:
            更新された状態。
        """


class InvestigationAgent(BaseAgent):
    """読み取り専用エージェント。情報を収集する。"""

    async def run(self, state: AgentState, guild: Any) -> AgentState:
        if "investigation_results" not in state:
            state["investigation_results"] = {}
        result = await self.investigate(state, guild)
        state["investigation_results"][self.name] = result
        return state

    @abstractmethod
    async def investigate(self, state: AgentState, guild: Any) -> dict[str, Any]:
        """対象の情報を収集する（読み取り専用）。

        Args:
            state: LangGraphワークフローの状態。
            guild: 対象のDiscordサーバー。

        Returns:
            収集結果の辞書。
        """


class ExecutionAgent(BaseAgent):
    """書き込みエージェント。ユーザー承認後に変更操作を実行する。"""

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
        """変更操作を実行する。

        Args:
            state: LangGraphワークフローの状態。
            guild: 対象のDiscordサーバー。

        Returns:
            実行結果の辞書。
        """
