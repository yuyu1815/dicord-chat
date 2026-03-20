"""Tests for the LangGraph pre-approval and post-approval workflows."""
from typing import Any
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from graph.workflow import (
    build_pre_approval_workflow,
    build_post_approval_workflow,
    DEFAULT_MAX_PLANNING_ITERATIONS,
)
from graph.state import AgentState


def _make_state(**overrides) -> AgentState:
    """テスト用の状態を作成するヘルパー。"""
    mock_bot = MagicMock()
    mock_bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    mock_bot.main_agent = MagicMock()

    state: AgentState = {
        "request": "Create a channel called test",
        "guild_id": 123456789,
        "channel_id": 4001,
        "user_id": 2001,
        "user_permissions": {"administrator": True},
        "bot": mock_bot,
    }
    state.update(overrides)
    return state


# --- Pre-approval workflow tests ---


@pytest.mark.asyncio
async def test_pre_approval_done_no_execution():
    """調査のみリクエストでplan_status=done_no_executionになること。"""
    planner = MagicMock()
    planner.plan_next_step = AsyncMock(return_value={
        "status": "done_no_execution",
        "investigation_targets": [],
        "execution_candidates": [],
        "replace_todos": False,
        "summary": "Info only",
    })

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = planner

    workflow = build_pre_approval_workflow()
    app = workflow.compile()
    result = await app.ainvoke(_make_state(bot=bot))

    assert result.get("plan_status") == "done_no_execution"
    assert result.get("approval_required") is False
    assert result.get("approval_status") == "none"
    assert result.get("proposed_todos") == []


@pytest.mark.asyncio
async def test_pre_approval_need_investigation_then_ready():
    """調査→追加調査→実行候補提示のループが動くこと。"""
    planner = MagicMock()
    planner.plan_next_step = AsyncMock(side_effect=[
        {
            "status": "need_investigation",
            "investigation_targets": ["channel"],
            "execution_candidates": [],
            "replace_todos": False,
            "summary": "Need channel info",
        },
        {
            "status": "ready_for_approval",
            "investigation_targets": [],
            "execution_candidates": [{"agent": "channel_execution", "action": "create", "params": {"name": "test"}}],
            "replace_todos": True,
            "summary": "Ready",
        },
    ])
    planner.build_investigation_todos.return_value = [{"agent": "channel_investigation", "action": "investigate", "params": {}}]
    planner.build_execution_todos.return_value = [{"agent": "channel_execution", "action": "create", "params": {"name": "test"}}]

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = planner

    with patch("graph.workflow.load_agent_module") as mock_load:
        mock_agent = MagicMock()
        mock_agent.name = "channel_investigation"
        mock_agent.run = AsyncMock(return_value={
            "investigation_results": {
                "channel_investigation": {"total_count": 5},
            },
        })
        mock_load.return_value = mock_agent

        workflow = build_pre_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(_make_state(bot=bot))

    assert result.get("plan_status") == "ready_for_approval"
    assert result.get("approval_required") is True
    assert result.get("planning_iteration") == 2
    assert "channel_investigation" in result.get("completed_investigation_agents", [])
    assert len(result.get("proposed_todos", [])) == 1


@pytest.mark.asyncio
async def test_pre_approval_max_iterations_with_execution_todos():
    """max_planning_iterationsに達し実行候補がある場合、approvalに進むこと。"""
    planner = MagicMock()
    # Last iteration returns ready_for_approval so there are execution todos
    planner.plan_next_step = AsyncMock(side_effect=[
        {
            "status": "need_investigation",
            "investigation_targets": ["channel"],
            "execution_candidates": [],
            "replace_todos": False,
            "summary": "Keep going",
        }
    ] * (DEFAULT_MAX_PLANNING_ITERATIONS - 1) + [
        {
            "status": "ready_for_approval",
            "investigation_targets": [],
            "execution_candidates": [{"agent": "channel_execution", "action": "create", "params": {"name": "test"}}],
            "replace_todos": True,
            "summary": "Ready",
        },
    ])
    planner.build_investigation_todos.return_value = [{"agent": "channel_investigation", "action": "investigate", "params": {}}]
    planner.build_execution_todos.return_value = [{"agent": "channel_execution", "action": "create", "params": {"name": "test"}}]

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = planner

    with patch("graph.workflow.load_agent_module") as mock_load:
        mock_agent = MagicMock()
        mock_agent.name = "channel_investigation"
        mock_agent.run = AsyncMock(return_value={
            "investigation_results": {
                "channel_investigation": {},
            },
        })
        mock_load.return_value = mock_agent

        workflow = build_pre_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(_make_state(bot=bot))

    assert result.get("plan_status") == "ready_for_approval"


@pytest.mark.asyncio
async def test_pre_approval_max_iterations_no_execution_todos():
    """max_planning_iterationsに達し実行候補がない場合、done_no_executionになること。"""
    planner = MagicMock()
    # Planner always wants to investigate, never produces execution candidates
    planner.plan_next_step = AsyncMock(side_effect=[
        {
            "status": "need_investigation",
            "investigation_targets": ["channel"],
            "execution_candidates": [],
            "replace_todos": False,
            "summary": "Keep going",
        }
        for _ in range(DEFAULT_MAX_PLANNING_ITERATIONS)
    ])
    # After first investigation completes, build_investigation_todos returns empty
    # (target already completed), so draft_todos stays empty from iteration 2 onward.
    planner.build_investigation_todos.side_effect = [
        [{"agent": "channel_investigation", "action": "investigate", "params": {}}],
    ] + [[] for _ in range(DEFAULT_MAX_PLANNING_ITERATIONS - 1)]

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = planner

    with patch("graph.workflow.load_agent_module") as mock_load:
        mock_agent = MagicMock()
        mock_agent.name = "channel_investigation"
        mock_agent.run = AsyncMock(return_value={
            "investigation_results": {
                "channel_investigation": {},
            },
        })
        mock_load.return_value = mock_agent

        workflow = build_pre_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(_make_state(bot=bot))

    assert result.get("plan_status") == "done_no_execution"
    assert result.get("approval_required") is False


@pytest.mark.asyncio
async def test_pre_approval_planner_error():
    """plannerがerrorを返したらfinalize_errorに進むこと。"""
    planner = MagicMock()
    planner.plan_next_step = AsyncMock(return_value={
        "status": "error",
        "investigation_targets": [],
        "execution_candidates": [],
        "replace_todos": False,
        "summary": "Cannot process request",
    })

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = planner

    workflow = build_pre_approval_workflow()
    app = workflow.compile()
    result = await app.ainvoke(_make_state(bot=bot))

    assert result.get("plan_status") == "error"
    assert "Cannot process request" in result.get("error", "")


@pytest.mark.asyncio
async def test_pre_approval_malformed_planner_output():
    """malformed planner output相当でも安全にエラーになること。"""
    planner = MagicMock()
    planner.plan_next_step = AsyncMock(return_value={
        "status": "error",
        "investigation_targets": [],
        "execution_candidates": [],
        "replace_todos": False,
        "summary": "Planner parsing failed",
    })

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = planner

    workflow = build_pre_approval_workflow()
    app = workflow.compile()
    result = await app.ainvoke(_make_state(bot=bot))

    assert result.get("plan_status") == "error"


@pytest.mark.asyncio
async def test_pre_approval_no_duplicate_investigations():
    """同じ調査が複数回実行されないこと。"""
    planner = MagicMock()
    planner.plan_next_step = AsyncMock(side_effect=[
        {
            "status": "need_investigation",
            "investigation_targets": ["channel", "role"],
            "execution_candidates": [],
            "replace_todos": False,
            "summary": "Need info",
        },
        {
            "status": "need_investigation",
            "investigation_targets": ["channel"],
            "execution_candidates": [],
            "replace_todos": False,
            "summary": "Need more",
        },
        {
            "status": "ready_for_approval",
            "investigation_targets": [],
            "execution_candidates": [{"agent": "channel_execution", "action": "create", "params": {"name": "test"}}],
            "replace_todos": True,
            "summary": "Done investigating",
        },
    ])
    planner.build_investigation_todos.side_effect = [
        [
            {"agent": "channel_investigation", "action": "investigate", "params": {}},
            {"agent": "role_investigation", "action": "investigate", "params": {}},
        ],
        [],
    ]
    planner.build_execution_todos.return_value = [{"agent": "channel_execution", "action": "create", "params": {"name": "test"}}]

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = planner

    def mock_load(target, kind):
        agent = MagicMock()
        agent.name = f"{target}_{kind}"
        agent.run = AsyncMock(return_value={
            "investigation_results": {
                f"{target}_{kind}": {"data": "mock"},
            },
        })
        return agent

    with patch("graph.workflow.load_agent_module", side_effect=mock_load):
        workflow = build_pre_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(_make_state(bot=bot))

    completed = result.get("completed_investigation_agents", [])
    assert completed.count("channel_investigation") == 1


@pytest.mark.asyncio
async def test_pre_approval_draft_todos_replaced():
    """replace_todos=trueでdraft_todosが差し替わること。"""
    planner = MagicMock()
    planner.plan_next_step = AsyncMock(side_effect=[
        {
            "status": "need_investigation",
            "investigation_targets": ["channel"],
            "execution_candidates": [],
            "replace_todos": False,
            "summary": "Check channels",
        },
        {
            "status": "ready_for_approval",
            "investigation_targets": [],
            "execution_candidates": [{"agent": "role_execution", "action": "create", "params": {"name": "Admin"}}],
            "replace_todos": True,
            "summary": "Replace plan",
        },
    ])
    planner.build_investigation_todos.return_value = [{"agent": "channel_investigation", "action": "investigate", "params": {}}]
    planner.build_execution_todos.return_value = [{"agent": "role_execution", "action": "create", "params": {"name": "Admin"}}]

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = planner

    with patch("graph.workflow.load_agent_module") as mock_load:
        mock_agent = MagicMock()
        mock_agent.name = "channel_investigation"
        mock_agent.run = AsyncMock(return_value={
            "investigation_results": {"channel_investigation": {}},
        })
        mock_load.return_value = mock_agent

        workflow = build_pre_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(_make_state(bot=bot))

    proposed = result.get("proposed_todos", [])
    assert len(proposed) == 1
    assert proposed[0]["agent"] == "role_execution"


@pytest.mark.asyncio
async def test_pre_approval_llm_unavailable():
    """bot.main_agentがない場合にエラーになること。"""
    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = None

    workflow = build_pre_approval_workflow()
    app = workflow.compile()
    result = await app.ainvoke(_make_state(bot=bot))

    assert result.get("plan_status") == "error"
    assert "LLM not available" in result.get("error", "")


# --- Post-approval workflow tests ---


@pytest.mark.asyncio
async def test_post_approval_approved_runs_execution():
    """承認時に実行エージェントが動くこと。"""
    state = _make_state(
        approval_status="approved",
        proposed_todos=[
            {"agent": "channel_execution", "action": "create", "params": {"name": "test"}},
        ],
        approved=True,
    )

    with patch("graph.workflow.load_agent_module") as mock_load:
        mock_agent = MagicMock()
        mock_agent.name = "channel_execution"
        mock_agent.run = AsyncMock(return_value={
            "execution_results": {
                "channel_execution": {"success": True, "details": "Created test"},
            },
        })
        mock_load.return_value = mock_agent

        workflow = build_post_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(state)

    assert result.get("plan_status") == "completed"
    assert "channel_execution" in result.get("execution_results", {})


@pytest.mark.asyncio
async def test_post_approval_rejected_no_execution():
    """拒否時に実行エージェントが動かないこと。"""
    state = _make_state(
        approval_status="rejected",
        proposed_todos=[
            {"agent": "channel_execution", "action": "create", "params": {"name": "test"}},
        ],
    )

    with patch("graph.workflow.load_agent_module") as mock_load:
        mock_load.return_value = MagicMock()

        workflow = build_post_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(state)

    assert result.get("plan_status") == "completed"
    assert result.get("execution_results", {}) == {}
    assert "cancelled" in result.get("final_response", "").lower()


@pytest.mark.asyncio
async def test_post_approval_uses_frozen_proposed_todos():
    """承認後は凍結されたproposed_todosが使われること。"""
    state = _make_state(
        approval_status="approved",
        proposed_todos=[
            {"agent": "channel_execution", "action": "create", "params": {"name": "frozen"}},
        ],
        # draft_todos differs from proposed_todos
        draft_todos=[
            {"agent": "role_execution", "action": "create", "params": {"name": "modified"}},
        ],
        approved=True,
    )

    executed_agents = []

    def mock_load(target, kind):
        agent = MagicMock()
        agent.name = f"{target}_{kind}"
        executed_agents.append(f"{target}_{kind}")

        async def run(state, guild):
            return {
                "execution_results": {
                    f"{target}_{kind}": {"success": True},
                },
            }
        agent.run = run
        return agent

    with patch("graph.workflow.load_agent_module", side_effect=mock_load):
        workflow = build_post_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(state)

    # Only proposed_todos (channel_execution) should be executed, not draft_todos (role_execution)
    assert "channel_execution" in executed_agents
    assert "role_execution" not in executed_agents


@pytest.mark.asyncio
async def test_post_approval_no_execution_todos():
    """実行タスクがない場合でも完了すること。"""
    state = _make_state(
        approval_status="approved",
        proposed_todos=[
            {"agent": "channel_investigation", "action": "investigate", "params": {}},
        ],
        approved=True,
    )

    workflow = build_post_approval_workflow()
    app = workflow.compile()
    result = await app.ainvoke(state)

    assert result.get("plan_status") == "completed"


@pytest.mark.asyncio
async def test_post_approval_execution_error():
    """実行エージェントのエラーが結果に記録されること。"""
    state = _make_state(
        approval_status="approved",
        proposed_todos=[
            {"agent": "channel_execution", "action": "create", "params": {"name": "test"}},
        ],
        approved=True,
    )

    with patch("graph.workflow.load_agent_module") as mock_load:
        mock_agent = MagicMock()
        mock_agent.name = "channel_execution"
        mock_agent.run = AsyncMock(side_effect=RuntimeError("Discord API error"))
        mock_load.return_value = mock_agent

        workflow = build_post_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(state)

    assert "channel_execution" in result.get("execution_results", {})
    assert "Discord API error" in str(result["execution_results"]["channel_execution"])


# --- Fix 1: ExecutionAgent must NOT call execute() when all permissions missing ---

from agents.base import ExecutionAgent
from graph.state import AgentState as _AgentState


class _StubExecutionAgent(ExecutionAgent):
    """Permission-gated execution agent stub for testing."""

    ACTION_PERMISSIONS = {"create": ["manage_channels"]}

    @property
    def name(self) -> str:
        return "stub_execution"

    async def execute(self, state: _AgentState, guild: Any) -> dict:
        return {"success": True, "details": "execute() was called"}


@pytest.mark.asyncio
async def test_execution_agent_skips_execute_when_all_blocked():
    """権限不足で全アクションがブロックされた場合、execute()が呼ばれないこと。"""
    agent = _StubExecutionAgent()
    state: _AgentState = {
        "approved": True,
        "todos": [
            {"agent": "stub_execution", "action": "create", "params": {"name": "x"}},
        ],
        "user_permissions": {"manage_channels": False, "administrator": False},
    }
    result_state = await agent.run(state, None)
    assert result_state["execution_results"]["stub_execution"]["success"] is False
    assert "execute() was called" not in result_state["execution_results"]["stub_execution"].get("details", "")
    assert len(result_state["execution_results"]["stub_execution"].get("permission_denied", [])) == 1


@pytest.mark.asyncio
async def test_execution_agent_calls_execute_with_admin():
    """管理者権限の場合はexecute()が呼ばれること。"""
    agent = _StubExecutionAgent()
    state: _AgentState = {
        "approved": True,
        "todos": [
            {"agent": "stub_execution", "action": "create", "params": {"name": "x"}},
        ],
        "user_permissions": {"administrator": True},
    }
    result_state = await agent.run(state, None)
    assert result_state["execution_results"]["stub_execution"]["success"] is True
    assert "execute() was called" in result_state["execution_results"]["stub_execution"]["details"]


@pytest.mark.asyncio
async def test_execution_agent_calls_execute_with_sufficient_perms():
    """必要な権限が揃っている場合、execute()が呼ばれること。"""
    agent = _StubExecutionAgent()
    state: _AgentState = {
        "approved": True,
        "todos": [
            {"agent": "stub_execution", "action": "create", "params": {"name": "x"}},
        ],
        "user_permissions": {"manage_channels": True, "administrator": False},
    }
    result_state = await agent.run(state, None)
    assert result_state["execution_results"]["stub_execution"]["success"] is True


@pytest.mark.asyncio
async def test_execution_agent_empty_agent_todos_still_calls_execute():
    """対象agentのtodoがない場合でも、空集合判定で誤って全ブロック扱いしないこと。"""
    agent = _StubExecutionAgent()
    state: _AgentState = {
        "approved": True,
        "todos": [
            {"agent": "other_execution", "action": "create", "params": {"name": "x"}},
        ],
        "user_permissions": {"manage_channels": False, "administrator": False},
    }
    result_state = await agent.run(state, None)
    assert result_state["execution_results"]["stub_execution"]["success"] is True
    assert result_state["execution_results"]["stub_execution"]["details"] == "execute() was called"


class _InspectingExecutionAgent(ExecutionAgent):
    ACTION_PERMISSIONS = {"create": ["manage_channels"]}

    @property
    def name(self) -> str:
        return "inspect_execution"

    async def execute(self, state: _AgentState, guild: Any) -> dict:
        mine = [t for t in state.get("todos", []) if t.get("agent") == self.name]
        return {"remaining_actions": [t.get("action") for t in mine]}


@pytest.mark.asyncio
async def test_execution_agent_filters_blocked_todos_before_execute():
    """部分的にブロックされたtodoがexecute()側に渡らないこと。"""
    agent = _InspectingExecutionAgent()
    state: _AgentState = {
        "approved": True,
        "todos": [
            {"agent": "inspect_execution", "action": "create", "params": {"name": "blocked"}},
            {"agent": "inspect_execution", "action": "noop", "params": {}},
        ],
        "user_permissions": {"manage_channels": False, "administrator": False},
    }
    result_state = await agent.run(state, None)
    assert result_state["execution_results"]["inspect_execution"]["remaining_actions"] == ["noop"]
    assert len(result_state["execution_results"]["inspect_execution"]["permission_denied"]) == 1


# --- Fix 4: done_no_execution state produces final_response ---

@pytest.mark.asyncio
async def test_pre_approval_done_no_execution_has_final_response():
    """done_no_executionの状態でfinal_responseが生成されること。"""
    planner = MagicMock()
    planner.plan_next_step = AsyncMock(return_value={
        "status": "done_no_execution",
        "investigation_targets": [],
        "execution_candidates": [],
        "replace_todos": False,
        "summary": "All info gathered",
    })

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = planner

    workflow = build_pre_approval_workflow()
    app = workflow.compile()
    result = await app.ainvoke(_make_state(bot=bot))

    assert result.get("final_response") == "All info gathered"
    assert result.get("plan_status") == "done_no_execution"


# --- Fix 6: Robust JSON parsing ---

from agents.main_agent import _parse_json_from_llm


def test_parse_json_plain():
    assert _parse_json_from_llm('{"status": "ok"}') == {"status": "ok"}


def test_parse_json_codeblock():
    assert _parse_json_from_llm('```json\n{"status": "ok"}\n```') == {"status": "ok"}


def test_parse_json_codeblock_no_lang():
    assert _parse_json_from_llm('```\n{"status": "ok"}\n```') == {"status": "ok"}


def test_parse_json_with_leading_text():
    text = 'Here is the result:\n```json\n{"status": "done"}\n```\nDone.'
    assert _parse_json_from_llm(text) == {"status": "done"}


def test_parse_json_with_trailing_text():
    text = '```json\n{"status": "done"}\n```\nExtra text after'
    assert _parse_json_from_llm(text) == {"status": "done"}


def test_parse_json_from_prose_without_fence():
    text = 'I analyzed the request. The result is {"status": "done", "summary": "wrapped in prose"}. Please continue.'
    assert _parse_json_from_llm(text) == {"status": "done", "summary": "wrapped in prose"}


def test_parse_json_from_prose_without_fence_nested_object():
    text = 'Reasoning first. {"status": "done", "meta": {"count": 2, "ok": true}} trailing notes.'
    assert _parse_json_from_llm(text) == {"status": "done", "meta": {"count": 2, "ok": True}}


def test_parse_json_invalid_raises():
    import pytest as _pytest
    with _pytest.raises(ValueError):
        _parse_json_from_llm("not json")


# --- Fix 1: run_execution deduplicates agents per todo ---


@pytest.mark.asyncio
async def test_post_approval_execution_deduplicates_same_agent():
    """同じ実行エージェントが複数todoで複数回呼ばれないこと。"""
    state = _make_state(
        approval_status="approved",
        proposed_todos=[
            {"agent": "channel_execution", "action": "create", "params": {"name": "a"}},
            {"agent": "channel_execution", "action": "create", "params": {"name": "b"}},
            {"agent": "channel_execution", "action": "delete", "params": {"name": "c"}},
        ],
        approved=True,
    )

    call_count = 0

    with patch("graph.workflow.load_agent_module") as mock_load:
        mock_agent = MagicMock()
        mock_agent.name = "channel_execution"

        async def fake_run(state, guild):
            nonlocal call_count
            call_count += 1
            return {
                "execution_results": {
                    "channel_execution": {"success": True, "calls": call_count},
                },
            }

        mock_agent.run = fake_run
        mock_load.return_value = mock_agent

        workflow = build_post_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(state)

    assert call_count == 1, f"Expected 1 call but got {call_count}"
    assert result.get("plan_status") == "completed"


@pytest.mark.asyncio
async def test_post_approval_execution_different_agents_each_run_once():
    """異なる実行エージェントがそれぞれ1回ずつ呼ばれること。"""
    state = _make_state(
        approval_status="approved",
        proposed_todos=[
            {"agent": "channel_execution", "action": "create", "params": {"name": "a"}},
            {"agent": "role_execution", "action": "create", "params": {"name": "mod"}},
        ],
        approved=True,
    )

    call_log = []

    def mock_load(target, kind):
        agent = MagicMock()
        agent.name = f"{target}_{kind}"

        async def fake_run(state, guild):
            call_log.append(agent.name)
            return {"execution_results": {agent.name: {"success": True}}}

        agent.run = fake_run
        return agent

    with patch("graph.workflow.load_agent_module", side_effect=mock_load):
        workflow = build_post_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(state)

    assert call_log == ["channel_execution", "role_execution"]
    assert result.get("plan_status") == "completed"


# --- Fix 2: investigation failures are NOT marked completed ---


@pytest.mark.asyncio
async def test_pre_approval_failed_investigation_not_marked_completed():
    """調査エージェントが失敗した場合、completed_investigation_agentsに追加されないこと。"""
    planner = MagicMock()
    planner.plan_next_step = AsyncMock(side_effect=[
        {
            "status": "need_investigation",
            "investigation_targets": ["channel"],
            "execution_candidates": [],
            "replace_todos": False,
            "summary": "Need channel info",
        },
        {
            "status": "ready_for_approval",
            "investigation_targets": [],
            "execution_candidates": [{"agent": "channel_execution", "action": "create", "params": {"name": "test"}}],
            "replace_todos": True,
            "summary": "Ready",
        },
    ])
    planner.build_investigation_todos.return_value = [
        {"agent": "channel_investigation", "action": "investigate", "params": {}},
    ]
    planner.build_execution_todos.return_value = [
        {"agent": "channel_execution", "action": "create", "params": {"name": "test"}},
    ]

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = planner

    with patch("graph.workflow.load_agent_module") as mock_load:
        mock_agent = MagicMock()
        mock_agent.name = "channel_investigation"
        mock_agent.run = AsyncMock(side_effect=RuntimeError("Agent crash"))
        mock_load.return_value = mock_agent

        workflow = build_pre_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(_make_state(bot=bot))

    completed = result.get("completed_investigation_agents", [])
    assert "channel_investigation" not in completed
    inv_results = result.get("investigation_results", {})
    assert "error" in inv_results.get("channel_investigation", {})


@pytest.mark.asyncio
async def test_pre_approval_unavailable_investigation_not_marked_completed():
    """調査エージェントが読み込み不可の場合、completedに追加されないこと。"""
    planner = MagicMock()
    planner.plan_next_step = AsyncMock(side_effect=[
        {
            "status": "need_investigation",
            "investigation_targets": ["channel"],
            "execution_candidates": [],
            "replace_todos": False,
            "summary": "Need channel info",
        },
        {
            "status": "done_no_execution",
            "investigation_targets": [],
            "execution_candidates": [],
            "replace_todos": False,
            "summary": "Could not investigate",
        },
    ])
    planner.build_investigation_todos.return_value = [
        {"agent": "channel_investigation", "action": "investigate", "params": {}},
    ]

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = planner

    with patch("graph.workflow.load_agent_module", return_value=None):
        workflow = build_pre_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(_make_state(bot=bot))

    completed = result.get("completed_investigation_agents", [])
    assert "channel_investigation" not in completed
    inv_results = result.get("investigation_results", {})
    assert "error" in inv_results.get("channel_investigation", {})


@pytest.mark.asyncio
async def test_pre_approval_successful_investigation_is_marked_completed():
    """調査エージェントが成功した場合のみcompletedに追加されること。"""
    planner = MagicMock()
    planner.plan_next_step = AsyncMock(side_effect=[
        {
            "status": "need_investigation",
            "investigation_targets": ["channel"],
            "execution_candidates": [],
            "replace_todos": False,
            "summary": "Need channel info",
        },
        {
            "status": "done_no_execution",
            "investigation_targets": [],
            "execution_candidates": [],
            "replace_todos": False,
            "summary": "Got it",
        },
    ])
    planner.build_investigation_todos.return_value = [
        {"agent": "channel_investigation", "action": "investigate", "params": {}},
    ]

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = planner

    with patch("graph.workflow.load_agent_module") as mock_load:
        mock_agent = MagicMock()
        mock_agent.name = "channel_investigation"
        mock_agent.run = AsyncMock(return_value={
            "investigation_results": {"channel_investigation": {"total_count": 3}},
        })
        mock_load.return_value = mock_agent

        workflow = build_pre_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(_make_state(bot=bot))

    completed = result.get("completed_investigation_agents", [])
    assert "channel_investigation" in completed


# --- Fix 3: empty approval todos routes to done_no_execution ---


@pytest.mark.asyncio
async def test_pre_approval_empty_todos_at_max_iterations():
    """max_iterations到達時にdraft_todosが空ならdone_no_executionになること。"""
    planner = MagicMock()
    planner.plan_next_step = AsyncMock(side_effect=[
        {
            "status": "need_investigation",
            "investigation_targets": ["channel"],
            "execution_candidates": [],
            "replace_todos": False,
            "summary": "Keep going",
        }
        for _ in range(DEFAULT_MAX_PLANNING_ITERATIONS)
    ])
    # First iteration has investigation todos; subsequent ones are empty
    # (simulating all targets already completed)
    planner.build_investigation_todos.side_effect = [
        [{"agent": "channel_investigation", "action": "investigate", "params": {}}],
    ] + [[] for _ in range(DEFAULT_MAX_PLANNING_ITERATIONS - 1)]

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = planner

    with patch("graph.workflow.load_agent_module") as mock_load:
        mock_agent = MagicMock()
        mock_agent.name = "channel_investigation"
        mock_agent.run = AsyncMock(return_value={
            "investigation_results": {"channel_investigation": {}},
        })
        mock_load.return_value = mock_agent

        workflow = build_pre_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(_make_state(bot=bot))

    assert result.get("plan_status") == "done_no_execution"
    assert result.get("approval_required") is False


# --- Fix: Invalid LLM execution candidates must not silently become done_no_execution ---


@pytest.mark.asyncio
async def test_pre_approval_ready_for_approval_all_candidates_filtered_becomes_error():
    """plannerがready_for_approvalを返しても全候補がフィルタリングされた場合、エラーになること。"""
    planner = MagicMock()
    planner.plan_next_step = AsyncMock(return_value={
        "status": "ready_for_approval",
        "investigation_targets": [],
        "execution_candidates": [
            {"agent": "nonexistent_execution", "action": "create", "params": {}},
        ],
        "replace_todos": True,
        "summary": "Should create something",
    })
    # build_execution_todos filters out nonexistent agent -> empty list
    planner.build_execution_todos.return_value = []

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = planner

    workflow = build_pre_approval_workflow()
    app = workflow.compile()
    result = await app.ainvoke(_make_state(bot=bot))

    assert result.get("plan_status") == "error"
    assert result.get("approval_required") is False
    assert "filtered out" in result.get("error", "")


@pytest.mark.asyncio
async def test_pre_approval_ready_for_approval_valid_candidates_succeeds():
    """plannerが有効な候補を返した場合はready_for_approvalになること。"""
    planner = MagicMock()
    planner.plan_next_step = AsyncMock(return_value={
        "status": "ready_for_approval",
        "investigation_targets": [],
        "execution_candidates": [
            {"agent": "channel_execution", "action": "create", "params": {"name": "test"}},
        ],
        "replace_todos": True,
        "summary": "Create channel",
    })
    planner.build_execution_todos.return_value = [
        {"agent": "channel_execution", "action": "create", "params": {"name": "test"}},
    ]

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = planner

    workflow = build_pre_approval_workflow()
    app = workflow.compile()
    result = await app.ainvoke(_make_state(bot=bot))

    assert result.get("plan_status") == "ready_for_approval"
    assert result.get("approval_required") is True


# --- Fix: Non-result state updates from agents are preserved ---


@pytest.mark.asyncio
async def test_investigation_extra_state_fields_preserved():
    """調査エージェントが返す非結果フィールドがワークフロー状態にマージされること。"""
    planner = MagicMock()
    planner.plan_next_step = AsyncMock(side_effect=[
        {
            "status": "need_investigation",
            "investigation_targets": ["channel"],
            "execution_candidates": [],
            "replace_todos": False,
            "summary": "Need info",
        },
        {
            "status": "done_no_execution",
            "investigation_targets": [],
            "execution_candidates": [],
            "replace_todos": False,
            "summary": "Done",
        },
    ])
    planner.build_investigation_todos.return_value = [
        {"agent": "channel_investigation", "action": "investigate", "params": {}},
    ]

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = planner

    with patch("graph.workflow.load_agent_module") as mock_load:
        mock_agent = MagicMock()
        mock_agent.name = "channel_investigation"
        mock_agent.run = AsyncMock(return_value={
            "investigation_results": {
                "channel_investigation": {"total_count": 5},
            },
            "investigation_summary": "Agent-level summary: 5 channels found",
        })
        mock_load.return_value = mock_agent

        workflow = build_pre_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(_make_state(bot=bot))

    # The investigation_summary from the agent should be merged into state.
    assert result.get("investigation_summary") is not None
    assert "channel_investigation" in result.get("investigation_results", {})


@pytest.mark.asyncio
async def test_execution_extra_state_fields_preserved():
    """実行エージェントが返す非結果フィールドが最終状態にマージされること。"""
    state = _make_state(
        approval_status="approved",
        proposed_todos=[
            {"agent": "channel_execution", "action": "create", "params": {"name": "test"}},
        ],
        approved=True,
    )

    with patch("graph.workflow.load_agent_module") as mock_load:
        mock_agent = MagicMock()
        mock_agent.name = "channel_execution"
        mock_agent.run = AsyncMock(return_value={
            "execution_results": {
                "channel_execution": {"success": True},
            },
            "investigation_summary": "Post-execution summary from agent",
        })
        mock_load.return_value = mock_agent

        workflow = build_post_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(state)

    assert result.get("plan_status") == "completed"
    # The extra investigation_summary from the execution agent should be merged
    assert result.get("investigation_summary") == "Post-execution summary from agent"


@pytest.mark.asyncio
async def test_agent_return_approval_keys_not_merged():
    """エージェントが返す承認関連キーがマージされないこと。"""
    planner = MagicMock()
    planner.plan_next_step = AsyncMock(side_effect=[
        {
            "status": "need_investigation",
            "investigation_targets": ["channel"],
            "execution_candidates": [],
            "replace_todos": False,
            "summary": "Need info",
        },
        {
            "status": "done_no_execution",
            "investigation_targets": [],
            "execution_candidates": [],
            "replace_todos": False,
            "summary": "Done",
        },
    ])
    planner.build_investigation_todos.return_value = [
        {"agent": "channel_investigation", "action": "investigate", "params": {}},
    ]

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = planner

    with patch("graph.workflow.load_agent_module") as mock_load:
        mock_agent = MagicMock()
        mock_agent.name = "channel_investigation"
        # Agent returns approval_required=True but it must NOT be merged
        mock_agent.run = AsyncMock(return_value={
            "investigation_results": {
                "channel_investigation": {"data": "ok"},
            },
            "approval_required": True,
            "approval_status": "approved",
            "plan_status": "executing",
        })
        mock_load.return_value = mock_agent

        workflow = build_pre_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(_make_state(bot=bot))

    # Frozen approval keys must NOT be overwritten by agent returns
    assert result.get("approval_required") is False
    assert result.get("approval_status") == "none"
    assert result.get("plan_status") == "done_no_execution"


# --- Fix: Approval persistence with todos_hash verification ---


from cogs.agent_cog import _compute_todos_hash, ApprovalView


def test_compute_todos_hash_deterministic():
    """同じtodos入力から同じハッシュが生成されること。"""
    todos = [
        {"agent": "channel_execution", "action": "create", "params": {"name": "test"}},
    ]
    h1 = _compute_todos_hash(todos)
    h2 = _compute_todos_hash(todos)
    assert h1 == h2
    assert isinstance(h1, str)
    assert len(h1) == 16


def test_compute_todos_hash_differs_for_different_todos():
    """異なるtodos入力から異なるハッシュが生成されること。"""
    todos_a = [{"agent": "channel_execution", "action": "create", "params": {"name": "a"}}]
    todos_b = [{"agent": "channel_execution", "action": "create", "params": {"name": "b"}}]
    assert _compute_todos_hash(todos_a) != _compute_todos_hash(todos_b)


def test_compute_todos_hash_empty_list():
    """空リストでもハッシュが生成されること。"""
    h = _compute_todos_hash([])
    assert isinstance(h, str)
    assert len(h) == 16


@pytest.mark.asyncio
async def test_verify_approval_returns_false_when_no_record():
    """DBに承認レコードがない場合、_verify_approvalがFalseを返すこと。"""
    bot = MagicMock()
    bot.config = {"database_url": "sqlite:///database/test_verify_none.db"}
    view = ApprovalView.__new__(ApprovalView)
    view.bot = bot
    view.approval_id = "nonexistent-id"
    view.state = {"proposed_todos": []}

    result = await view._verify_approval()
    assert result is False


@pytest.mark.asyncio
async def test_verify_approval_returns_false_on_hash_mismatch():
    """ハッシュが一致しない場合、_verify_approvalがFalseを返すこと。"""
    import tempfile
    import os

    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    try:
        bot = MagicMock()
        bot.config = {"database_url": f"sqlite:///{db_path}"}
        approval_id = "test-mismatch-id"

        original_todos = [{"agent": "channel_execution", "action": "create", "params": {"name": "original"}}]
        original_hash = _compute_todos_hash(original_todos)

        import aiosqlite
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS approvals (id TEXT PRIMARY KEY, approved INTEGER NOT NULL, user_id INTEGER NOT NULL, created_at TEXT NOT NULL, todos_hash TEXT)",
            )
            await db.execute(
                "INSERT INTO approvals (id, approved, user_id, created_at, todos_hash) VALUES (?, ?, ?, datetime('now'), ?)",
                (approval_id, 1, 1001, original_hash),
            )
            await db.commit()

        view = ApprovalView.__new__(ApprovalView)
        view.bot = bot
        view.approval_id = approval_id
        view.state = {
            "proposed_todos": [{"agent": "role_execution", "action": "create", "params": {"name": "tampered"}}],
        }

        result = await view._verify_approval()
        assert result is False
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_verify_approval_returns_true_on_match():
    """ハッシュが一致する場合、_verify_approvalがTrueを返すこと。"""
    import tempfile
    import os

    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    try:
        bot = MagicMock()
        bot.config = {"database_url": f"sqlite:///{db_path}"}
        approval_id = "test-match-id"

        todos = [{"agent": "channel_execution", "action": "create", "params": {"name": "ok"}}]
        todos_hash = _compute_todos_hash(todos)

        import aiosqlite
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS approvals (id TEXT PRIMARY KEY, approved INTEGER NOT NULL, user_id INTEGER NOT NULL, created_at TEXT NOT NULL, todos_hash TEXT)",
            )
            await db.execute(
                "INSERT INTO approvals (id, approved, user_id, created_at, todos_hash) VALUES (?, ?, ?, datetime('now'), ?)",
                (approval_id, 1, 1001, todos_hash),
            )
            await db.commit()

        view = ApprovalView.__new__(ApprovalView)
        view.bot = bot
        view.approval_id = approval_id
        view.state = {"proposed_todos": todos}

        result = await view._verify_approval()
        assert result is True
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_verify_approval_returns_false_when_not_approved():
    """DBでapproved=0の場合、_verify_approvalがFalseを返すこと。"""
    import tempfile
    import os

    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    try:
        bot = MagicMock()
        bot.config = {"database_url": f"sqlite:///{db_path}"}
        approval_id = "test-rejected-id"

        todos = [{"agent": "channel_execution", "action": "create", "params": {"name": "x"}}]
        todos_hash = _compute_todos_hash(todos)

        import aiosqlite
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS approvals (id TEXT PRIMARY KEY, approved INTEGER NOT NULL, user_id INTEGER NOT NULL, created_at TEXT NOT NULL, todos_hash TEXT)",
            )
            await db.execute(
                "INSERT INTO approvals (id, approved, user_id, created_at, todos_hash) VALUES (?, ?, ?, datetime('now'), ?)",
                (approval_id, 0, 1001, todos_hash),
            )
            await db.commit()

        view = ApprovalView.__new__(ApprovalView)
        view.bot = bot
        view.approval_id = approval_id
        view.state = {"proposed_todos": todos}

        result = await view._verify_approval()
        assert result is False
    finally:
        os.unlink(db_path)


# --- Fix: single-action execution agents rejected when proposed multiple todos ---


@pytest.mark.asyncio
async def test_pre_approval_single_action_agent_multiple_todos_rejected():
    """single-actionエージェントに複数todoが提案された場合、エラーになること。"""
    planner = MagicMock()
    planner.plan_next_step = AsyncMock(return_value={
        "status": "ready_for_approval",
        "investigation_targets": [],
        "execution_candidates": [
            {"agent": "emoji_execution", "action": "create", "params": {"name": "a"}},
            {"agent": "emoji_execution", "action": "delete", "params": {"name": "b"}},
        ],
        "replace_todos": True,
        "summary": "Manage emojis",
    })
    planner.build_execution_todos.return_value = [
        {"agent": "emoji_execution", "action": "create", "params": {"name": "a"}},
        {"agent": "emoji_execution", "action": "delete", "params": {"name": "b"}},
    ]

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = planner

    workflow = build_pre_approval_workflow()
    app = workflow.compile()
    result = await app.ainvoke(_make_state(bot=bot))

    assert result.get("plan_status") == "error"
    assert result.get("approval_required") is False
    assert "single-action" in result.get("error", "").lower()
    assert "emoji_execution" in result.get("error", "")


@pytest.mark.asyncio
async def test_pre_approval_multiple_single_action_agents_each_multi_rejected():
    """複数のsingle-actionエージェントがそれぞれ複数todoを持つ場合、全てリジェクトされること。"""
    planner = MagicMock()
    planner.plan_next_step = AsyncMock(return_value={
        "status": "ready_for_approval",
        "investigation_targets": [],
        "execution_candidates": [
            {"agent": "emoji_execution", "action": "create", "params": {"name": "a"}},
            {"agent": "emoji_execution", "action": "create", "params": {"name": "b"}},
            {"agent": "sticker_execution", "action": "create", "params": {"name": "c"}},
            {"agent": "sticker_execution", "action": "create", "params": {"name": "d"}},
        ],
        "replace_todos": True,
        "summary": "Create stuff",
    })
    planner.build_execution_todos.return_value = [
        {"agent": "emoji_execution", "action": "create", "params": {"name": "a"}},
        {"agent": "emoji_execution", "action": "create", "params": {"name": "b"}},
        {"agent": "sticker_execution", "action": "create", "params": {"name": "c"}},
        {"agent": "sticker_execution", "action": "create", "params": {"name": "d"}},
    ]

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = planner

    workflow = build_pre_approval_workflow()
    app = workflow.compile()
    result = await app.ainvoke(_make_state(bot=bot))

    assert result.get("plan_status") == "error"
    error = result.get("error", "")
    assert "emoji_execution" in error
    assert "sticker_execution" in error


@pytest.mark.asyncio
async def test_pre_approval_multi_action_agent_multiple_todos_allowed():
    """multi-actionエージェント（channel_execution等）に複数todoがあっても許可されること。"""
    planner = MagicMock()
    planner.plan_next_step = AsyncMock(return_value={
        "status": "ready_for_approval",
        "investigation_targets": [],
        "execution_candidates": [
            {"agent": "channel_execution", "action": "create", "params": {"name": "a"}},
            {"agent": "channel_execution", "action": "delete", "params": {"name": "b"}},
        ],
        "replace_todos": True,
        "summary": "Manage channels",
    })
    planner.build_execution_todos.return_value = [
        {"agent": "channel_execution", "action": "create", "params": {"name": "a"}},
        {"agent": "channel_execution", "action": "delete", "params": {"name": "b"}},
    ]

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = planner

    workflow = build_pre_approval_workflow()
    app = workflow.compile()
    result = await app.ainvoke(_make_state(bot=bot))

    assert result.get("plan_status") == "ready_for_approval"
    assert result.get("approval_required") is True


@pytest.mark.asyncio
async def test_pre_approval_single_action_agent_single_todo_allowed():
    """single-actionエージェントにtodoが1つだけの場合は許可されること。"""
    planner = MagicMock()
    planner.plan_next_step = AsyncMock(return_value={
        "status": "ready_for_approval",
        "investigation_targets": [],
        "execution_candidates": [
            {"agent": "emoji_execution", "action": "create", "params": {"name": "party"}},
        ],
        "replace_todos": True,
        "summary": "Create emoji",
    })
    planner.build_execution_todos.return_value = [
        {"agent": "emoji_execution", "action": "create", "params": {"name": "party"}},
    ]

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = planner

    workflow = build_pre_approval_workflow()
    app = workflow.compile()
    result = await app.ainvoke(_make_state(bot=bot))

    assert result.get("plan_status") == "ready_for_approval"
    assert result.get("approval_required") is True


@pytest.mark.asyncio
async def test_pre_approval_all_single_action_agents_tested():
    """_SINGLE_ACTION_EXECUTION_AGENTSに含まれる全エージェントが拒否されること。"""
    from graph.workflow import _SINGLE_ACTION_EXECUTION_AGENTS

    for agent_name in _SINGLE_ACTION_EXECUTION_AGENTS:
        planner = MagicMock()
        planner.plan_next_step = AsyncMock(return_value={
            "status": "ready_for_approval",
            "investigation_targets": [],
            "execution_candidates": [
                {"agent": agent_name, "action": "create", "params": {"name": "a"}},
                {"agent": agent_name, "action": "delete", "params": {"name": "b"}},
            ],
            "replace_todos": True,
            "summary": "Test",
        })
        planner.build_execution_todos.return_value = [
            {"agent": agent_name, "action": "create", "params": {"name": "a"}},
            {"agent": agent_name, "action": "delete", "params": {"name": "b"}},
        ]

        bot = MagicMock()
        bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
        bot.main_agent = planner

        workflow = build_pre_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(_make_state(bot=bot))

        assert result.get("plan_status") == "error", (
            f"Agent {agent_name} with 2 todos should have been rejected"
        )
