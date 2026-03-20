"""Tests for the LangGraph pre-approval and post-approval workflows."""
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
    state: AgentState = {
        "request": "Create a channel called test",
        "guild_id": 123456789,
        "channel_id": 4001,
        "user_id": 2001,
        "user_permissions": {"administrator": True},
    }
    state.update(overrides)
    return state


def _mock_llm_response(content: str) -> MagicMock:
    """LLMレスポンスのモックを作成する。"""
    return MagicMock(content=content)


# --- Pre-approval workflow tests ---


@pytest.mark.asyncio
async def test_pre_approval_done_no_execution():
    """調査のみリクエストでapproval_required=Falseになること。"""
    llm_response = '{"status": "done_no_execution", "investigation_targets": [], "execution_candidates": [], "summary": "Info only"}'

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=_mock_llm_response(llm_response))

    with patch("graph.workflow._get_llm", return_value=mock_llm):
        workflow = build_pre_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(_make_state())

    assert result.get("plan_status") == "ready_for_approval"
    assert result.get("approval_required") is False
    assert result.get("approval_status") == "pending"
    assert result.get("proposed_todos") == []


@pytest.mark.asyncio
async def test_pre_approval_need_investigation_then_ready():
    """調査→追加調査→実行候補提示のループが動くこと。"""
    # 1st call: need investigation
    first_response = '{"status": "need_investigation", "investigation_targets": ["channel"], "execution_candidates": [], "replace_todos": false, "summary": "Need channel info"}'

    # 2nd call: ready for approval (investigations are mocked as already completed)
    second_response = '{"status": "ready_for_approval", "investigation_targets": [], "execution_candidates": [{"agent": "channel_execution", "action": "create", "params": {"name": "test"}}], "replace_todos": true, "summary": "Ready"}'

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=[
        _mock_llm_response(first_response),
        _mock_llm_response(second_response),
    ])

    with patch("graph.workflow._get_llm", return_value=mock_llm):
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
            result = await app.ainvoke(_make_state())

    assert result.get("plan_status") == "ready_for_approval"
    assert result.get("approval_required") is True
    assert result.get("planning_iteration") == 2
    assert "channel_investigation" in result.get("completed_investigation_agents", [])
    assert len(result.get("proposed_todos", [])) == 1


@pytest.mark.asyncio
async def test_pre_approval_max_iterations():
    """max_planning_iterationsに達したら強制的にapprovalに進むこと。"""
    need_investigation = '{"status": "need_investigation", "investigation_targets": ["channel"], "execution_candidates": [], "replace_todos": false, "summary": "Keep going"}'

    # max_iterations + 1 回分のレスポンス
    responses = [_mock_llm_response(need_investigation)] * (DEFAULT_MAX_PLANNING_ITERATIONS + 1)

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=responses)

    with patch("graph.workflow._get_llm", return_value=mock_llm):
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
            result = await app.ainvoke(_make_state())

    assert result.get("plan_status") == "ready_for_approval"
    assert result.get("planning_iteration") == DEFAULT_MAX_PLANNING_ITERATIONS


@pytest.mark.asyncio
async def test_pre_approval_planner_error():
    """plannerがerrorを返したらfinalize_errorに進むこと。"""
    error_response = '{"status": "error", "summary": "Cannot process request"}'

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=_mock_llm_response(error_response))

    with patch("graph.workflow._get_llm", return_value=mock_llm):
        workflow = build_pre_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(_make_state())

    assert result.get("plan_status") == "error"
    assert "Cannot process request" in result.get("error", "")


@pytest.mark.asyncio
async def test_pre_approval_malformed_planner_output():
    """malformed LLM出力でも安全にエラーになること。"""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=_mock_llm_response("totally not json"))

    with patch("graph.workflow._get_llm", return_value=mock_llm):
        workflow = build_pre_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(_make_state())

    assert result.get("plan_status") == "error"


@pytest.mark.asyncio
async def test_pre_approval_no_duplicate_investigations():
    """同じ調査が複数回実行されないこと。"""
    # 1st call: investigate channel
    first_response = '{"status": "need_investigation", "investigation_targets": ["channel", "role"], "execution_candidates": [], "replace_todos": false, "summary": "Need info"}'

    # 2nd call: try to investigate channel again (should be skipped by planner)
    second_response = '{"status": "need_investigation", "investigation_targets": ["channel"], "execution_candidates": [], "replace_todos": false, "summary": "Need more"}'

    # 3rd call: ready
    third_response = '{"status": "ready_for_approval", "investigation_targets": [], "execution_candidates": [], "replace_todos": true, "summary": "Done investigating"}'

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=[
        _mock_llm_response(first_response),
        _mock_llm_response(second_response),
        _mock_llm_response(third_response),
    ])

    call_count = {"channel": 0, "role": 0}

    def mock_load(target, kind):
        agent = MagicMock()
        agent.name = f"{target}_{kind}"
        agent.run = AsyncMock(return_value={
            "investigation_results": {
                f"{target}_{kind}": {"data": "mock"},
            },
        })
        return agent

    with patch("graph.workflow._get_llm", return_value=mock_llm):
        with patch("cogs.agent_cog._load_agent_module", side_effect=mock_load):
            workflow = build_pre_approval_workflow()
            app = workflow.compile()
            result = await app.ainvoke(_make_state())

    completed = result.get("completed_investigation_agents", [])
    # channel should appear only once (from first call)
    assert completed.count("channel_investigation") == 1


@pytest.mark.asyncio
async def test_pre_approval_draft_todos_replaced():
    """replace_todos=trueでdraft_todosが差し替わること。"""
    # 1st call: need investigation
    first_response = '{"status": "need_investigation", "investigation_targets": ["channel"], "execution_candidates": [], "replace_todos": false, "summary": "Check channels"}'

    # 2nd call: ready with replace_todos=true
    second_response = '{"status": "ready_for_approval", "investigation_targets": [], "execution_candidates": [{"agent": "role_execution", "action": "create", "params": {"name": "Admin"}}], "replace_todos": true, "summary": "Replace plan"}'

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=[
        _mock_llm_response(first_response),
        _mock_llm_response(second_response),
    ])

    with patch("graph.workflow._get_llm", return_value=mock_llm):
        with patch("cogs.agent_cog._load_agent_module") as mock_load:
            mock_agent = MagicMock()
            mock_agent.name = "channel_investigation"
            mock_agent.run = AsyncMock(return_value={
                "investigation_results": {"channel_investigation": {}},
            })
            mock_load.return_value = mock_agent

            workflow = build_pre_approval_workflow()
            app = workflow.compile()
            result = await app.ainvoke(_make_state())

    proposed = result.get("proposed_todos", [])
    assert len(proposed) == 1
    assert proposed[0]["agent"] == "role_execution"


@pytest.mark.asyncio
async def test_pre_approval_llm_unavailable():
    """LLMが利用不可の場合にエラーになること。"""
    with patch("graph.workflow._get_llm", return_value=None):
        workflow = build_pre_approval_workflow()
        app = workflow.compile()
        result = await app.ainvoke(_make_state())

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
    assert "execution_channel" in result.get("execution_results", {})


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

    assert "execution_channel" in result.get("execution_results", {})
    assert "Discord API error" in str(result["execution_results"]["execution_channel"])
