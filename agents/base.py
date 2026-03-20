from abc import ABC, abstractmethod
import logging
from typing import Any

import discord
from discord import HTTPException

from agents.log import log_agent_call
from graph.state import AgentState
from i18n import t

logger = logging.getLogger("discord_bot")


def _find_action(state: AgentState, agent_name: str) -> str | None:
    """単一アクションエージェント用のヘルパー。最初のマッチするtodoのアクション名を返す。

    Args:
        state: LangGraphワークフローの状態。
        agent_name: エージェントの一意識別子。

    Returns:
        マッチするアクション名、なければ ``None``。
    """
    for todo in state.get("todos", []):
        if todo.get("agent") == agent_name and not todo.get("_blocked"):
            return todo.get("action")
    return None


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
        await log_agent_call(self.name, "investigation.run.start", state, guild=guild)
        result = await self.investigate(state, guild)
        state["investigation_results"][self.name] = result
        await log_agent_call(self.name, "investigation.run.end", state, guild=guild, result=result)
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
    """書き込みエージェント。ユーザー承認後に変更操作を実行する。

    Attributes:
        single_action: ``True`` の場合、このエージェントは実行時に
            最初のマッチするtodoのみ処理する。プランナーは
            このエージェントに対して todo を1つしか生成してはならない。
    """

    ACTION_PERMISSIONS: dict[str, list[str]] = {}
    single_action: bool = False

    async def run(self, state: AgentState, guild: Any) -> AgentState:
        if not state.get("approved"):
            raise PermissionError(f"[{self.name}] Execution requires user approval.")

        await log_agent_call(self.name, "execution.run.start", state, guild=guild)
        user_perms = state.get("user_permissions", {})
        has_admin = user_perms.get("administrator", False)
        agent_todos = [todo for todo in state.get("todos", []) if todo.get("agent") == self.name]
        denied: list[dict[str, str]] = []
        blocked_count = 0

        if not has_admin and self.ACTION_PERMISSIONS:
            for todo in agent_todos:
                action = todo.get("action", "")
                required = self.ACTION_PERMISSIONS.get(action, [])
                missing = [p for p in required if not user_perms.get(p, False)]
                if missing:
                    todo["_blocked"] = True
                    blocked_count += 1
                    denied.append({
                        "action": action,
                        "message": t("perm.denied", locale=state.get("locale", "en"), permissions=", ".join(missing)),
                    })

        if "execution_results" not in state:
            state["execution_results"] = {}

        if agent_todos and blocked_count == len(agent_todos):
            result: dict[str, Any] = {
                "success": False,
                "permission_denied": denied,
                "details": t("perm.all_blocked", locale=state.get("locale", "en")),
            }
            state["execution_results"][self.name] = result
            await log_agent_call(self.name, "execution.run.blocked", state, guild=guild, result=result)
            return state

        execution_state = dict(state)
        execution_state["todos"] = [
            todo for todo in state.get("todos", [])
            if todo.get("agent") != self.name or not todo.get("_blocked")
        ]

        result = await self.execute(execution_state, guild)

        if denied:
            existing = result.get("permission_denied", [])
            result["permission_denied"] = existing + denied

        state["execution_results"][self.name] = result
        await log_agent_call(self.name, "execution.run.end", execution_state, guild=guild, result=result)
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


class SingleActionExecutionAgent(ExecutionAgent):
    """単一アクション実行エージェントのテンプレート基底クラス。

    ``execute()`` メソッドを提供し、最初のマッチするtodoを検索して
    ``_do_<action>`` メソッドにディスパッチする。サブクラスは以下を定義する：

    * ``name`` プロパティ
    * ``ACTION_HANDLERS`` クラス変数 (action名 -> 説明の辞書)
    * ``_do_<action>(guild, params)`` メソッド群

    Attributes:
        not_found_message: ``discord.NotFound`` 時の詳細メッセージ。
    """

    single_action: bool = True
    ACTION_HANDLERS: dict[str, str] = {}
    not_found_message: str = "Target not found."

    async def execute(self, state: AgentState, guild: Any) -> dict[str, Any]:
        self._locale = state.get("locale", "en")
        action_name = _find_action(state, self.name)
        if not action_name:
            return {"success": False, "action": "none", "details": t("err.no_matching_todo", locale=self._locale)}

        if action_name not in self.ACTION_HANDLERS:
            return {"success": False, "action": action_name, "details": t("err.unknown_action", locale=self._locale, action=action_name)}

        params = next(
            (t["params"] for t in state["todos"] if t.get("agent") == self.name and t.get("action") == action_name),
            {},
        )
        await log_agent_call(self.name, "execution.action.start", state, guild=guild, action=action_name)

        try:
            result = await getattr(self, f"_do_{action_name}")(guild, params)
            await log_agent_call(self.name, "execution.action.end", state, guild=guild, action=action_name, result=result)
            return result
        except PermissionError:
            raise
        except Exception as exc:
            result = self._handle_error(exc, action_name)
            await log_agent_call(self.name, "execution.action.error", state, guild=guild, action=action_name, result=result)
            return result

    def _handle_error(self, exc: Exception, action_name: str) -> dict[str, Any]:
        """例外を結果辞書に変換する。

        Args:
            exc: 発生した例外。
            action_name: 実行中のアクション名。

        Returns:
            エラー結果の辞書。
        """
        locale = getattr(self, "_locale", "en")
        if isinstance(exc, discord.Forbidden):
            return {"success": False, "action": action_name, "details": t("err.missing_permissions", locale=locale)}
        if isinstance(exc, discord.NotFound):
            return {"success": False, "action": action_name, "details": self.not_found_message}
        if isinstance(exc, HTTPException):
            return {"success": False, "action": action_name, "details": t("err.api_error", locale=locale, text=exc.text)}
        logger.warning("Unexpected error in %s/%s: %s", self.name, action_name, exc)
        return {"success": False, "action": action_name, "details": t("err.unexpected", locale=locale, error=exc)}


class MultiActionExecutionAgent(ExecutionAgent):
    """複数アクション実行エージェントのテンプレート基底クラス。

    ``execute()`` メソッドを提供し、ブロックされていない全todoを反復処理し、
    ``_dispatch()`` メソッドで各アクションのハンドラに振り分ける。
    サブクラスは以下を定義する：

    * ``name`` プロパティ
    * ``_dispatch(action, params, guild)`` メソッド
    """

    async def execute(self, state: AgentState, guild: Any) -> dict[str, Any]:
        self._locale = state.get("locale", "en")
        todos = state.get("todos", [])
        my_todos = [t for t in todos if t.get("agent") == self.name and not t.get("_blocked")]
        if not my_todos:
            return {"success": False, "action": "none", "details": t("err.no_matching_action", locale=self._locale)}

        results = []
        for todo in my_todos:
            action = todo.get("action", "")
            params = todo.get("params", {})
            await log_agent_call(self.name, "execution.action.start", state, guild=guild, action=action)
            result = await self._dispatch(action, params, guild)
            await log_agent_call(self.name, "execution.action.end", state, guild=guild, action=action, result=result)
            results.append(result)

        details = "; ".join(r["details"] for r in results)
        all_ok = all(r["success"] for r in results)
        return {"success": all_ok, "action": ", ".join(r["action"] for r in results), "details": details}

    @abstractmethod
    async def _dispatch(self, action: str, params: dict, guild: Any) -> dict[str, Any]:
        """アクション名に対応するハンドラに振り分ける。

        Args:
            action: アクション名。
            params: アクションのパラメータ。
            guild: 対象のDiscordサーバー。

        Returns:
            実行結果の辞書。
        """
