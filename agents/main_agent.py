import json
import logging
import re
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from agents.log import log_ai_exchange
from agents.prompts import PLANNING_SYSTEM_PROMPT, SYSTEM_PROMPT
from agents.registry import (
    EXECUTION_TARGETS,
    INVESTIGATION_TARGETS,
    get_execution_agent_names,
)
from graph.state import (
    VALID_PLANNER_STATUSES,
    AgentState,
    PLANNER_STATUS_DONE_NO_EXECUTION,
    PLANNER_STATUS_ERROR,
    PLANNER_STATUS_NEED_INVESTIGATION,
    PLANNER_STATUS_READY_FOR_APPROVAL,
    Todo,
    agent_target_from_name,
)

logger = logging.getLogger("discord_bot")


def _extract_usage(response: Any) -> dict[str, int]:
    """LLMレスポンスからトークン使用量を抽出する。

    Args:
        response: LangChain AIMessage。

    Returns:
        input_tokens, output_tokens, cache_read, cache_creation, reasoning を含む辞書。
    """
    usage: dict[str, int] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read": 0,
        "cache_creation": 0,
        "reasoning": 0,
    }
    meta = getattr(response, "usage_metadata", None)
    if isinstance(meta, dict):
        usage["input_tokens"] = meta.get("input_tokens", 0) or 0
        usage["output_tokens"] = meta.get("output_tokens", 0) or 0
        details = meta.get("input_token_details") or {}
        if isinstance(details, dict):
            usage["cache_read"] = details.get("cache_read", 0) or 0
            usage["cache_creation"] = details.get("cache_creation", 0) or 0
        out_details = meta.get("output_token_details") or {}
        if isinstance(out_details, dict):
            usage["reasoning"] = out_details.get("reasoning", 0) or 0

    # Anthropic thinking tokens (not mapped by LangChain into usage_metadata)
    resp_meta = getattr(response, "response_metadata", None)
    if isinstance(resp_meta, dict):
        raw_usage = resp_meta.get("usage") or {}
        if isinstance(raw_usage, dict) and "thinking_tokens" in raw_usage:
            usage["reasoning"] = raw_usage["thinking_tokens"]

    return usage


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
        agents_str = ", ".join(get_execution_agent_names())
        prompt = SYSTEM_PROMPT.format(
            investigation_targets=targets_str,
            execution_agents=agents_str,
        )

        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=state["request"]),
        ]
        try:
            response = await self.llm.ainvoke(messages)
            parsed = _parse_json_from_llm(response.content)
            await log_ai_exchange(
                "parse_request",
                state,
                messages,
                response_text=response.content,
                parsed=parsed,
                usage=_extract_usage(response),
            )
            return parsed
        except Exception as e:
            await log_ai_exchange(
                "parse_request",
                state,
                messages,
                error=str(e),
            )
            logger.error("Failed to parse request with LLM: %s", e)
            return {"investigation_targets": [], "execution_candidates": [], "todos": []}

    def build_todos(self, parsed: dict[str, Any]) -> list[Todo]:
        """LLMの解析結果を構造化されたタスクリストに変換する。

        Args:
            parsed: :meth:`parse_request` の戻り値。

        Returns:
            各タスクのエージェント名・アクション・パラメータを含むリスト。
        """
        todos: list[Todo] = []
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
        agents_str = ", ".join(get_execution_agent_names())

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

        # Build history section for prompt
        history = state.get("conversation_history", [])
        if history:
            history_lines = []
            for i, turn in enumerate(history, 1):
                history_lines.append(
                    f"Turn {i} (session_id: {turn['session_id']}):\n"
                    f"  User request: {turn['request']}\n"
                    f"  Bot response: {turn['response']}"
                )
            history_section = (
                "The user has had these previous conversations in this server:\n"
                + "\n".join(history_lines)
                + "\nIf the user's current request references a previous "
                "conversation, use status 'need_history_detail' with the "
                "matching session_id to load detailed logs.\n"
            )
        else:
            history_section = ""

        # Include history detail if previously loaded
        history_detail = state.get("history_detail")
        if history_detail:
            context_parts.append("Detailed logs for the requested session:\n" + history_detail)

        prompt = PLANNING_SYSTEM_PROMPT.format(
            investigation_targets=targets_str,
            execution_agents=agents_str,
            history_section=history_section,
        )

        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content="\n\n".join(context_parts)),
        ]
        try:
            response = await self.llm.ainvoke(messages)
            decision = _parse_json_from_llm(response.content)
            validated = _validate_planner_decision(decision)
            await log_ai_exchange(
                "plan_next_step",
                state,
                messages,
                response_text=response.content,
                parsed=validated,
                usage=_extract_usage(response),
            )
            return validated
        except Exception as e:
            await log_ai_exchange(
                "plan_next_step",
                state,
                messages,
                error=str(e),
            )
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
    ) -> list[Todo]:
        """調査対象のリストから調査タスクリストを生成する。

        既に完了済みの調査はスキップする。

        Args:
            targets: 調査対象のリスト。
            state: 現在のワークフロー状態。

        Returns:
            調査タスクリスト。
        """
        completed = set(state.get("completed_investigation_agents", []))
        todos: list[Todo] = []
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
    ) -> list[Todo]:
        """実行候補のリストから実行タスクリストを生成する。

        Args:
            candidates: 実行候補のリスト。

        Returns:
            実行タスクリスト。
        """
        if not isinstance(candidates, list):
            return []
        todos: list[Todo] = []
        for candidate in candidates:
            agent = candidate.get("agent", "")
            target = agent_target_from_name(agent)
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
    valid_statuses = VALID_PLANNER_STATUSES
    status = decision.get("status", PLANNER_STATUS_ERROR)

    if status not in valid_statuses:
        status = PLANNER_STATUS_ERROR

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

    # need_history_detail does not require targets/candidates
    session_id = decision.get("session_id", "")

    if status == PLANNER_STATUS_READY_FOR_APPROVAL and not candidates:
        status = PLANNER_STATUS_ERROR
        summary = summary or "No execution candidates provided for approval."

    if status == PLANNER_STATUS_NEED_INVESTIGATION and not targets:
        status = PLANNER_STATUS_ERROR
        summary = summary or "No investigation targets specified."

    return {
        "status": status,
        "investigation_targets": targets,
        "execution_candidates": candidates,
        "replace_todos": replace,
        "summary": summary,
        "session_id": session_id,
    }
