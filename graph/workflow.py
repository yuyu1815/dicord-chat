import logging
from typing import Any

from langgraph.graph import END, StateGraph

from graph.state import AgentState

logger = logging.getLogger("discord_bot")

DEFAULT_MAX_PLANNING_ITERATIONS = 5


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
        from agents.main_agent import MainAgent

        llm = _get_llm()
        if not llm:
            return {"plan_status": "error", "error": "LLM not available"}

        planner = MainAgent(llm)
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
                "plan_status": "ready_for_approval",
                "approval_required": False,
                "approval_summary": decision.get("summary", ""),
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
        from cogs.agent_cog import _load_agent_module

        investigation_todos = state.get("pending_investigation_todos", [])

        if not investigation_todos:
            return {"plan_status": "planning", "pending_investigation_todos": []}

        investigation_state = dict(state)
        investigation_state["todos"] = investigation_todos

        try:
            results: dict[str, Any] = {}
            for todo in investigation_todos:
                agent_name = todo.get("agent", "")
                target = agent_name.replace("_investigation", "")
                agent = _load_agent_module(target, "investigation")
                if not agent:
                    continue
                try:
                    new_state = await agent.run(investigation_state, None)
                    key = f"investigation_{target}"
                    results[key] = new_state.get(
                        "investigation_results", {},
                    ).get(agent.name, {})
                except Exception as e:
                    logger.error("Investigation agent %s failed: %s", agent_name, e)
                    results[f"investigation_{target}"] = {"error": str(e)}

            merged_results = dict(state.get("investigation_results", {}))
            merged_results.update(results)

            completed = list(state.get("completed_investigation_agents", []))
            for todo in investigation_todos:
                agent_name = todo.get("agent", "")
                if agent_name not in completed:
                    completed.append(agent_name)

            summary_parts = []
            for key, value in results.items():
                text = str(value)[:200]
                summary_parts.append(f"- {key}: {text}")

            return {
                "investigation_results": merged_results,
                "completed_investigation_agents": completed,
                "investigation_summary": "\n".join(summary_parts),
                "pending_investigation_todos": [],
                "plan_status": "planning",
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

        return {
            "proposed_todos": draft_todos,
            "todos": draft_todos,
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

    # --- エッジ ---
    workflow.add_edge("initialize_request", "plan_next_step")

    def after_plan(state: AgentState) -> str:
        plan_status = state.get("plan_status", "")
        if plan_status == "investigating":
            return "run_investigations"
        if plan_status == "ready_for_approval":
            return "prepare_approval"
        return "finalize_error"

    workflow.add_conditional_edges("plan_next_step", after_plan, {
        "run_investigations": "run_investigations",
        "prepare_approval": "prepare_approval",
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

    workflow.add_edge("prepare_approval", END)
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
        from cogs.agent_cog import _load_agent_module

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
            results: dict[str, Any] = {}
            for todo in execution_todos:
                agent_name = todo.get("agent", "")
                target = agent_name.replace("_execution", "")
                agent = _load_agent_module(target, "execution")
                if not agent:
                    continue
                try:
                    new_state = await agent.run(execution_state, None)
                    key = f"execution_{target}"
                    results[key] = new_state.get(
                        "execution_results", {},
                    ).get(agent.name, {})
                except Exception as e:
                    logger.error("Execution agent %s failed: %s", agent_name, e)
                    results[f"execution_{target}"] = {"error": str(e)}

            merged_results = dict(state.get("execution_results", {}))
            merged_results.update(results)

            return {
                "execution_results": merged_results,
                "plan_status": "completed",
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


def _get_llm():
    """LLMインスタンスを取得する。"""
    try:
        import os

        from langchain_openai import ChatOpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL")
        model = os.environ.get("LLM_MODEL", "gpt-4o")
        if base_url:
            return ChatOpenAI(api_key=api_key, base_url=base_url, model=model)
        return ChatOpenAI(api_key=api_key, model=model)
    except Exception as e:
        logger.error("Failed to initialize LLM: %s", e)
        return None
