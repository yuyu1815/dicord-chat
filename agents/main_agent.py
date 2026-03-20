import json
import logging
import re
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from graph.state import AgentState

logger = logging.getLogger("discord_bot")


def _extract_first_json_object(text: str) -> str:
    """文字列中から最初のトップレベルJSONオブジェクトを抽出する。"""
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escape = False

        for index in range(start, len(text)):
            char = text[index]

            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]

        start = text.find("{", start + 1)

    raise ValueError("No JSON object found in LLM response")



def _parse_json_from_llm(text: str) -> dict[str, Any]:
    """LLMの出力からJSONオブジェクトを抽出・パースする。

    fenced code block、生JSON、前後に説明文があるJSONを扱う。

    Args:
        text: LLMのレスポンステキスト。

    Returns:
        パースされた辞書。パース失敗時は :class:`ValueError` を送出する。
    """
    text = text.strip()

    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    candidate = match.group(1).strip() if match else text

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        parsed = json.loads(_extract_first_json_object(candidate))

    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object from LLM response")
    return parsed

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
{{
  "investigation_targets": ["server", "channel", ...],
  "execution_candidates": [
    {{"agent": "channel_execution", "action": "create", "params": {{"name": "...", ...}}}}
  ]
}}

Available investigation targets: {investigation_targets}
Available execution agents: {execution_agents}

Rules:
- Only include targets that are actually needed
- If the request is read-only (checking info), execution_candidates should be empty
- Be specific with params for execution candidates
- Only use agents that actually exist in the list above
"""

PLANNING_SYSTEM_PROMPT = """You are a Discord server management planner.
Based on the user request and investigation results so far, decide the next step.

Respond ONLY with a JSON object with this structure:
{{
  "status": "need_investigation" | "ready_for_approval" | "done_no_execution" | "error",
  "investigation_targets": ["server", "channel", ...],
  "execution_candidates": [
    {{"agent": "channel_execution", "action": "create", "params": {{"name": "...", ...}}}}
  ],
  "replace_todos": true | false,
  "summary": "Brief description of what you decided and why"
}}

Available investigation targets: {investigation_targets}
Available execution agents: {execution_agents}

Rules:
- status "need_investigation": more info needed before proposing execution. Include new investigation_targets.
- status "ready_for_approval": ready to show execution candidates to the user for approval.
- status "done_no_execution": the request is purely informational, no execution needed.
- status "error": something went wrong or the request cannot be fulfilled.
- Only include investigation_targets that haven't been completed yet.
- Do NOT repeat investigations that already have results.
- replace_todos=true: replace all draft todos with new ones. false: append new todos to existing.
- execution_candidates must use the format {{"agent": "<target>_execution", "action": "...", "params": {{...}}}}
- CRITICAL: Never propose execution actions before investigation is complete.
- CRITICAL: Only use agents that actually exist in the list above.
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
            return _parse_json_from_llm(response.content)
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

    async def plan_next_step(self, state: AgentState) -> dict[str, Any]:
        """現在の状態から次の計画ステップを決定する。

        Args:
            state: 現在のワークフロー状態。

        Returns:
            プランナーの判断を含む辞書。
            status, investigation_targets, execution_candidates, replace_todos, summary を含む。
        """
        targets_str = ", ".join(INVESTIGATION_TARGETS)
        agents_str = ", ".join(f"{t}_execution" for t in EXECUTION_TARGETS)

        completed = state.get("completed_investigation_agents", [])
        results = state.get("investigation_results", {})
        draft_todos = state.get("draft_todos", [])
        iteration = state.get("planning_iteration", 0)

        context_parts = [
            f"User request: {state.get('request', '')}",
            f"Planning iteration: {iteration + 1}",
        ]

        if completed:
            context_parts.append(f"Completed investigations: {', '.join(completed)}")

        if results:
            results_summary_parts = []
            for key, value in results.items():
                text = str(value)
                if len(text) > 500:
                    text = text[:500] + "..."
                results_summary_parts.append(f"  {key}: {text}")
            context_parts.append("Investigation results:\n" + "\n".join(results_summary_parts))

        if draft_todos:
            todos_summary = []
            for todo in draft_todos:
                agent = todo.get("agent", "unknown")
                action = todo.get("action", "unknown")
                params = todo.get("params", {})
                param_str = ", ".join(f"{k}={v}" for k, v in params.items())
                todos_summary.append(f"  [{agent}] {action}({param_str})")
            context_parts.append("Current draft todos:\n" + "\n".join(todos_summary))

        prompt = PLANNING_SYSTEM_PROMPT.format(
            investigation_targets=targets_str,
            execution_agents=agents_str,
        )

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=prompt),
                HumanMessage(content="\n\n".join(context_parts)),
            ])
            decision = _parse_json_from_llm(response.content)
            return _validate_planner_decision(decision)
        except Exception as e:
            logger.error("Failed to plan next step with LLM: %s", e)
            return {
                "status": "error",
                "investigation_targets": [],
                "execution_candidates": [],
                "replace_todos": False,
                "summary": f"Planner error: {e}",
            }

    def build_investigation_todos(
        self, targets: list[str], state: AgentState,
    ) -> list[dict[str, Any]]:
        """調査対象のリストから調査タスクリストを生成する。

        既に完了済みの調査はスキップする。

        Args:
            targets: 調査対象のリスト。
            state: 現在のワークフロー状態。

        Returns:
            調査タスクリスト。
        """
        completed = set(state.get("completed_investigation_agents", []))
        todos: list[dict[str, Any]] = []
        for target in targets:
            agent_name = f"{target}_investigation"
            if agent_name not in completed and target in INVESTIGATION_TARGETS:
                todos.append({
                    "agent": agent_name,
                    "action": "investigate",
                    "params": {},
                })
        return todos

    def build_execution_todos(
        self, candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """実行候補のリストから実行タスクリストを生成する。

        Args:
            candidates: 実行候補のリスト。

        Returns:
            実行タスクリスト。
        """
        if not isinstance(candidates, list):
            return []
        todos: list[dict[str, Any]] = []
        for candidate in candidates:
            agent = candidate.get("agent", "")
            target = agent.replace("_execution", "")
            if target in EXECUTION_TARGETS and agent.endswith("_execution"):
                todos.append({
                    "agent": agent,
                    "action": candidate.get("action", ""),
                    "params": candidate.get("params", {}),
                })
        return todos


def _validate_planner_decision(decision: dict[str, Any]) -> dict[str, Any]:
    """プランナーの出力を検証し、安全なデフォルトで補完する。

    Args:
        decision: LLM出力の辞書。

    Returns:
        検証済みの判断辞書。
    """
    valid_statuses = {"need_investigation", "ready_for_approval", "done_no_execution", "error"}
    status = decision.get("status", "error")

    if status not in valid_statuses:
        status = "error"

    targets = decision.get("investigation_targets", [])
    if not isinstance(targets, list):
        targets = []

    candidates = decision.get("execution_candidates", [])
    if not isinstance(candidates, list):
        candidates = []

    replace = decision.get("replace_todos", False)
    if not isinstance(replace, bool):
        replace = False

    summary = decision.get("summary", "")

    if status == "ready_for_approval" and not candidates:
        status = "error"
        summary = summary or "No execution candidates provided for approval."

    if status == "need_investigation" and not targets:
        status = "error"
        summary = summary or "No investigation targets specified."

    return {
        "status": status,
        "investigation_targets": targets,
        "execution_candidates": candidates,
        "replace_todos": replace,
        "summary": summary,
    }
