import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from graph.state import AgentState

logger = logging.getLogger("discord_bot")

INVESTIGATION_TARGETS = [
    "server", "channel", "category", "thread", "forum",
    "message", "role", "permission", "member", "vc",
    "stage", "event", "automod", "invite", "webhook",
    "emoji", "sticker", "soundboard", "audit_log",
]

EXECUTION_TARGETS = [
    "server", "channel", "category", "thread", "forum",
    "message", "role", "permission", "member", "vc",
    "stage", "event", "automod", "invite", "webhook",
    "emoji", "sticker", "soundboard",
]

SYSTEM_PROMPT = """You are a Discord server management assistant.
Given a user request, determine which management areas are relevant and what actions are needed.

Respond ONLY with a JSON object with this structure:
{
  "investigation_targets": ["server", "channel", ...],
  "execution_candidates": [
    {"agent": "channel_execution", "action": "create", "params": {"name": "...", ...}}
  ]
}

Available investigation targets: {investigation_targets}
Available execution agents: {execution_targets}

Rules:
- Only include targets that are actually needed
- If the request is read-only (checking info), execution_candidates should be empty
- Be specific with params for execution candidates
- Only use agents that actually exist in the list above
"""


class MainAgent:
    """オーケストレーター。リクエストの解析・タスク分解・エージェントへの振り分けを行う。"""

    def __init__(self, llm: BaseChatModel) -> None:
        self.llm = llm

    async def parse_request(self, state: AgentState) -> dict[str, Any]:
        """LLMを使用して、どのエージェントを呼び出し、何のアクションを実行するかを判定する。

        Args:
            state: ユーザーリクエストを含むワークフロー状態。

        Returns:
            調査対象・実行候補・タスクリストを含む辞書。
        """
        if not state.get("request"):
            return {"investigation_targets": [], "execution_candidates": [], "todos": []}

        targets_str = ", ".join(INVESTIGATION_TARGETS)
        agents_str = ", ".join(f"{t}_execution" for t in EXECUTION_TARGETS)
        prompt = SYSTEM_PROMPT.format(
            investigation_targets=targets_str,
            execution_agents=agents_str,
        )

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=prompt),
                HumanMessage(content=state["request"]),
            ])
            import json
            return json.loads(response.content.strip().strip("```json").strip("```"))
        except Exception as e:
            logger.error("Failed to parse request with LLM: %s", e)
            return {"investigation_targets": [], "execution_candidates": [], "todos": []}

    def build_todos(self, parsed: dict[str, Any]) -> list[dict[str, Any]]:
        """LLMの解析結果を構造化されたタスクリストに変換する。

        Args:
            parsed: :meth:`parse_request` の戻り値。

        Returns:
            各タスクのエージェント名・アクション・パラメータを含むリスト。
        """
        todos: list[dict[str, Any]] = []
        for target in parsed.get("investigation_targets", []):
            todos.append({"agent": f"{target}_investigation", "action": "investigate", "params": {}})
        for candidate in parsed.get("execution_candidates", []):
            todos.append(candidate)
        return todos
