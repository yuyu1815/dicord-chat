import logging
from typing import Any

from langgraph.graph import END, StateGraph

from agents.registry import get_single_action_agents, load_agent_module
from graph.state import AgentState

logger = logging.getLogger("discord_bot")

DEFAULT_MAX_PLANNING_ITERATIONS = 5

# Derived from agent-declared single_action capability.
_SINGLE_ACTION_EXECUTION_AGENTS = get_single_action_agents()

# Keys from agent return state that are safe to merge back into the
# workflow state.  Approval-related keys are excluded so that the
# frozen approval semantics are never accidentally overwritten.
_MERGEABLE_STATE_KEYS = frozenset({
    "investigation_results",
    "execution_results",
    "investigation_summary",
})


def build_pre_approval_workflow() -> StateGraph:
    """承認前の計画・調査ループワークフローを構築する。

    ノード構成:
    - initialize_request: 状態の初期化
    - plan_next_step: LLMに次のステップを計画させる
    - run_investigations: 調査エージェントを実行
    - prepare_approval: 承認用にタスクを凍結し終了
    - finalize_response: エラー時の最終応答

    Returns:
        構築された :class:`StateGraph` インスタンス。
    """
    workflow = StateGraph(AgentState)
    workflow.set_entry_point("initialize_request")

    def initialize_request(state: AgentState) -> dict[str, Any]:
        """状態を初期化する。"""
        return {
            "plan_status": "planning",
            "planning_iteration": 0,
            "max_planning_iterations": DEFAULT_MAX_PLANNING_ITERATIONS,
            "planner_decision": {},
            "planning_history": [],
            "pending_investigation_todos": [],
            "completed_investigation_agents": [],
            "draft_todos": [],
            "proposed_todos": [],
            "todos_version": 0,
            "approval_required": False,
            "approval_status": "none",
            "approval_summary": "",
            "investigation_summary": "",
            "todos": [],
            "investigation_results": {},
            "execution_results": {},
            "error": None,
        }

    workflow.add_node("initialize_request", initialize_request)

    async def plan_next_step(state: AgentState) -> dict[str, Any]:
        """LLMに次の計画ステップを決定させる。"""
        bot = state.get("bot")
        planner = getattr(bot, "main_agent", None) if bot else None
        if not planner:
            return {"plan_status": "error", "error": "LLM not available"}

        decision = await planner.plan_next_step(state)

        iteration = state.get("planning_iteration", 0) + 1
        history = list(state.get("planning_history", []))
        history.append(decision)

        new_draft = list(state.get("draft_todos", []))

        if decision["status"] == "need_investigation":
            investigation_todos = planner.build_investigation_todos(
                decision["investigation_targets"], state,
            )
            if decision["replace_todos"]:
                new_draft = investigation_todos
            else:
                new_draft.extend(investigation_todos)
            return {
                "planner_decision": decision,
                "planning_iteration": iteration,
                "planning_history": history,
                "pending_investigation_todos": investigation_todos,
                "draft_todos": new_draft,
                "plan_status": "investigating",
                "approval_required": False,
            }
        elif decision["status"] == "ready_for_approval":
            execution_todos = planner.build_execution_todos(
                decision["execution_candidates"],
            )
            if not execution_todos:
                # Planner said ready but all candidates were filtered out
                # (e.g. invalid agent names). Fail closed instead of silently
                # falling through to done_no_execution.
                return {
                    "planner_decision": decision,
                    "planning_iteration": iteration,
                    "planning_history": history,
                    "draft_todos": new_draft,
                    "pending_investigation_todos": [],
                    "plan_status": "error",
                    "approval_required": False,
                    "approval_summary": decision.get("summary", ""),
                    "error": (
                        "Planner returned ready_for_approval but all execution "
                        "candidates were invalid and filtered out. Refusing to "
                        "proceed silently."
                    ),
                }
            if decision["replace_todos"]:
                new_draft = execution_todos
            else:
                new_draft.extend(execution_todos)
            return {
                "planner_decision": decision,
                "planning_iteration": iteration,
                "planning_history": history,
                "draft_todos": new_draft,
                "pending_investigation_todos": [],
                "plan_status": "ready_for_approval",
                "approval_required": True,
                "approval_summary": decision.get("summary", ""),
            }
        elif decision["status"] == "done_no_execution":
            return {
                "planner_decision": decision,
                "planning_iteration": iteration,
                "planning_history": history,
                "draft_todos": [],
                "pending_investigation_todos": [],
                "plan_status": "done_no_execution",
                "approval_required": False,
                "approval_summary": decision.get("summary", ""),
                "approval_status": "none",
            }
        else:
            return {
                "planner_decision": decision,
                "planning_iteration": iteration,
                "planning_history": history,
                "plan_status": "error",
                "error": decision.get("summary", "Unknown planner error"),
            }

    workflow.add_node("plan_next_step", plan_next_step)

    async def run_investigations(state: AgentState) -> dict[str, Any]:
        """調査エージェントを実行する。"""
        investigation_todos = state.get("pending_investigation_todos", [])

        if not investigation_todos:
            return {"plan_status": "planning", "pending_investigation_todos": []}

        investigation_state = dict(state)
        investigation_state["todos"] = investigation_todos

        try:
            bot = state.get("bot")
            guild = bot.get_guild(state.get("guild_id")) if bot else None

            results: dict[str, Any] = {}
            completed: list[str] = []
            extra_state: dict[str, Any] = {}
            for todo in investigation_todos:
                agent_name = todo.get("agent", "")
                target = agent_name.replace("_investigation", "")
                agent = load_agent_module(target, "investigation")
                if not agent:
                    logger.warning(
                        "Investigation agent %s not available", agent_name,
                    )
                    results[agent_name] = {
                        "error": f"Agent {agent_name} not available",
                    }
                    continue
                if not guild:
                    logger.warning("Guild %s not found for investigation %s", state.get("guild_id"), agent_name)
                    results[agent_name] = {"error": "Guild not found"}
                    continue
                try:
                    new_state = await agent.run(investigation_state, guild)
                    key = agent.name
                    results[key] = new_state.get(
                        "investigation_results", {},
                    ).get(agent.name, {})
                    # Preserve safe non-result state updates from the
                    # agent return so downstream nodes can see them.
                    for merge_key in _MERGEABLE_STATE_KEYS:
                        if merge_key in new_state and merge_key != "investigation_results":
                            extra_state.setdefault(merge_key, new_state[merge_key])
                    if key not in completed:
                        completed.append(key)
                except Exception as e:
                    logger.error("Investigation agent %s failed: %s", agent_name, e)
                    results[agent_name] = {"error": str(e)}

            merged_results = dict(state.get("investigation_results", {}))
            merged_results.update(results)

            new_completed = list(state.get("completed_investigation_agents", []))
            for c in completed:
                if c not in new_completed:
                    new_completed.append(c)

            summary_parts = []
            for key, value in results.items():
                text = str(value)[:200]
                summary_parts.append(f"- {key}: {text}")

            return {
                "investigation_results": merged_results,
                "completed_investigation_agents": new_completed,
                "investigation_summary": "\n".join(summary_parts),
                "pending_investigation_todos": [],
                "plan_status": "planning",
                **extra_state,
            }
        except Exception as e:
            logger.error("Failed to run investigations: %s", e)
            return {
                "plan_status": "error",
                "error": str(e),
                "pending_investigation_todos": [],
            }

    workflow.add_node("run_investigations", run_investigations)

    def prepare_approval(state: AgentState) -> dict[str, Any]:
        """承認用にタスクを凍結する。"""
        draft_todos = list(state.get("draft_todos", []))

        # Only execution todos are actionable; investigation-only drafts
        # should not enter approval.
        execution_drafts = [
            t for t in draft_todos if "investigation" not in t.get("agent", "")
        ]

        if not execution_drafts:
            return {
                "proposed_todos": [],
                "todos": [],
                "plan_status": "done_no_execution",
                "approval_required": False,
                "approval_status": "none",
                "approval_summary": state.get("approval_summary", ""),
            }

        # Fail closed: single-action agents can only process one todo.
        # If the planner proposed multiple todos for any of them, we must
        # reject the plan rather than silently dropping actions.
        from collections import Counter
        agent_counts = Counter(t.get("agent", "") for t in execution_drafts)
        multi = {
            name for name, count in agent_counts.items()
            if count > 1 and name in _SINGLE_ACTION_EXECUTION_AGENTS
        }
        if multi:
            agents_str = ", ".join(sorted(multi))
            logger.error(
                "Refusing to approve: single-action agents with multiple todos: %s",
                agents_str,
            )
            return {
                "proposed_todos": [],
                "todos": [],
                "plan_status": "error",
                "approval_required": False,
                "approval_status": "none",
                "error": (
                    f"Single-action execution agent(s) {agents_str} received "
                    "multiple proposed todos but can only process one each. "
                    "The planner must produce at most one todo per single-action "
                    "agent per cycle."
                ),
            }

        return {
            "proposed_todos": execution_drafts,
            "todos": execution_drafts,
            "todos_version": state.get("todos_version", 0) + 1,
            "approval_status": "pending",
            "plan_status": "ready_for_approval",
        }

    workflow.add_node("prepare_approval", prepare_approval)

    def finalize_error(state: AgentState) -> dict[str, Any]:
        """エラー時に最終応答を生成する。"""
        error = state.get("error", "Unknown error")
        return {
            "final_response": f"Error: {error}",
            "plan_status": "error",
        }

    workflow.add_node("finalize_error", finalize_error)

    def finalize_no_execution(state: AgentState) -> dict[str, Any]:
        """調査のみで実行不要な場合の最終応答を生成する。"""
        summary = state.get("approval_summary", state.get("investigation_summary", ""))
        parts = []
        inv_summary = state.get("investigation_summary", "")
        if inv_summary:
            parts.append(inv_summary)
        if summary and summary != inv_summary:
            parts.append(summary)
        return {
            "final_response": "\n\n".join(parts) if parts else "Investigation complete.",
            "plan_status": "done_no_execution",
        }

    workflow.add_node("finalize_no_execution", finalize_no_execution)

    # --- エッジ ---
    workflow.add_edge("initialize_request", "plan_next_step")

    def after_plan(state: AgentState) -> str:
        plan_status = state.get("plan_status", "")
        if plan_status == "investigating":
            return "run_investigations"
        if plan_status == "ready_for_approval":
            return "prepare_approval"
        if plan_status == "done_no_execution":
            return "finalize_no_execution"
        return "finalize_error"

    workflow.add_conditional_edges("plan_next_step", after_plan, {
        "run_investigations": "run_investigations",
        "prepare_approval": "prepare_approval",
        "finalize_no_execution": "finalize_no_execution",
        "finalize_error": "finalize_error",
    })

    def after_investigation(state: AgentState) -> str:
        plan_status = state.get("plan_status", "")
        if plan_status == "planning":
            iteration = state.get("planning_iteration", 0)
            max_iterations = state.get(
                "max_planning_iterations", DEFAULT_MAX_PLANNING_ITERATIONS,
            )
            if iteration >= max_iterations:
                return "prepare_approval"
            return "plan_next_step"
        return "finalize_error"

    workflow.add_conditional_edges("run_investigations", after_investigation, {
        "plan_next_step": "plan_next_step",
        "prepare_approval": "prepare_approval",
        "finalize_error": "finalize_error",
    })

    def after_approval(state: AgentState) -> str:
        plan_status = state.get("plan_status", "")
        if plan_status == "done_no_execution":
            return "finalize_no_execution"
        return END

    workflow.add_conditional_edges("prepare_approval", after_approval, {
        "finalize_no_execution": "finalize_no_execution",
        "__end__": END,
    })

    workflow.add_edge("finalize_no_execution", END)
    workflow.add_edge("finalize_error", END)

    return workflow


def build_post_approval_workflow() -> StateGraph:
    """承認後の実行ワークフローを構築する。

    入力状態に approval_status="approved" または "rejected" が設定されていること。

    Returns:
        構築された :class:`StateGraph` インスタンス。
    """
    workflow = StateGraph(AgentState)
    workflow.set_entry_point("check_approval")

    def check_approval(state: AgentState) -> dict[str, Any]:
        """承認状態を確認する。"""
        approval_status = state.get("approval_status", "none")
        if approval_status == "approved":
            return {"plan_status": "executing"}
        return {"plan_status": "completed"}

    workflow.add_node("check_approval", check_approval)

    async def run_execution(state: AgentState) -> dict[str, Any]:
        """実行エージェントを実行する。"""
        proposed_todos = state.get("proposed_todos", [])
        execution_todos = [
            t for t in proposed_todos if "investigation" not in t.get("agent", "")
        ]

        if not execution_todos:
            return {"plan_status": "completed", "execution_results": {}}

        execution_state = dict(state)
        execution_state["todos"] = execution_todos
        execution_state["approved"] = True

        try:
            bot = state.get("bot")
            guild = bot.get_guild(state.get("guild_id")) if bot else None

            results: dict[str, Any] = {}
            seen_agents: set[str] = set()
            extra_state: dict[str, Any] = {}
            for todo in execution_todos:
                agent_name = todo.get("agent", "")
                if agent_name in seen_agents:
                    continue
                seen_agents.add(agent_name)
                target = agent_name.replace("_execution", "")
                agent = load_agent_module(target, "execution")
                if not agent:
                    results[agent_name] = {"error": f"Agent {agent_name} not available"}
                    continue
                if not guild:
                    logger.warning("Guild %s not found for execution %s", state.get("guild_id"), agent_name)
                    results[agent.name] = {"error": "Guild not found"}
                    continue
                try:
                    new_state = await agent.run(execution_state, guild)
                    key = agent.name
                    results[key] = new_state.get(
                        "execution_results", {},
                    ).get(agent.name, {})
                    # Preserve safe non-result state updates from the
                    # agent return so downstream nodes can see them.
                    for merge_key in _MERGEABLE_STATE_KEYS:
                        if merge_key in new_state and merge_key != "execution_results":
                            extra_state.setdefault(merge_key, new_state[merge_key])
                except Exception as e:
                    logger.error("Execution agent %s failed: %s", agent_name, e)
                    results[agent_name] = {"error": str(e)}

            merged_results = dict(state.get("execution_results", {}))
            merged_results.update(results)

            return {
                "execution_results": merged_results,
                "plan_status": "completed",
                **extra_state,
            }
        except Exception as e:
            logger.error("Failed to run executions: %s", e)
            return {
                "plan_status": "error",
                "error": str(e),
            }

    workflow.add_node("run_execution", run_execution)

    def finalize_response(state: AgentState) -> dict[str, Any]:
        """最終応答を生成する。"""
        approval_status = state.get("approval_status", "")

        if approval_status == "rejected":
            return {
                "final_response": "Request cancelled by user.",
                "plan_status": "completed",
            }

        parts = []
        investigation_summary = state.get("investigation_summary", "")
        if investigation_summary:
            parts.append(investigation_summary)

        execution_results = state.get("execution_results", {})
        if execution_results:
            result_parts = []
            for key, value in execution_results.items():
                if isinstance(value, dict) and "error" in value:
                    result_parts.append(f"- {key}: ERROR - {value['error']}")
                else:
                    text = str(value)[:200]
                    result_parts.append(f"- {key}: {text}")
            parts.append("Execution results:\n" + "\n".join(result_parts))

        return {
            "final_response": "\n\n".join(parts) if parts else "Done.",
            "plan_status": "completed",
        }

    workflow.add_node("finalize_response", finalize_response)

    # --- エッジ ---
    def after_check(state: AgentState) -> str:
        plan_status = state.get("plan_status", "")
        if plan_status == "executing":
            return "run_execution"
        return "finalize_response"

    workflow.add_conditional_edges("check_approval", after_check, {
        "run_execution": "run_execution",
        "finalize_response": "finalize_response",
    })

    workflow.add_edge("run_execution", "finalize_response")
    workflow.add_edge("finalize_response", END)

    return workflow


def build_workflow() -> StateGraph:
    """後方互換性のためのスタブ。

    実際のオーケストレーションは :func:`build_pre_approval_workflow` と
    :func:`build_post_approval_workflow` を使用する。

    Returns:
        空の :class:`StateGraph` インスタンス。
    """
    return build_pre_approval_workflow()
