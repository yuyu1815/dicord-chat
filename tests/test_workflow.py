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

    with patch("cogs.agent_cog._load_agent_module") as mock_load:
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
async def test_pre_approval_max_iterations():
    """max_planning_iterationsに達したら強制的にapprovalに進むこと。"""
    planner = MagicMock()
    planner.plan_next_step = AsyncMock(side_effect=[
        {
            "status": "need_investigation",
            "investigation_targets": ["channel"],
            "execution_candidates": [],
            "replace_todos": False,
            "summary": "Keep going",
        }
    ] * (DEFAULT_MAX_PLANNING_ITERATIONS + 1))
    planner.build_investigation_todos.return_value = [{"agent": "channel_investigation", "action": "investigate", "params": {}}]

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=MagicMock(id=123456789))
    bot.main_agent = planner

    with patch("cogs.agent_cog._load_agent_module") as mock_load:
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
    assert result.get("planning_iteration") == DEFAULT_MAX_PLANNING_ITERATIONS


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

    with patch("cogs.agent_cog._load_agent_module", side_effect=mock_load):
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

    with patch("cogs.agent_cog._load_agent_module") as mock_load:
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

    with patch("cogs.agent_cog._load_agent_module") as mock_load:
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

    with patch("cogs.agent_cog._load_agent_module") as mock_load:
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

    with patch("cogs.agent_cog._load_agent_module", side_effect=mock_load):
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

    with patch("cogs.agent_cog._load_agent_module") as mock_load:
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
