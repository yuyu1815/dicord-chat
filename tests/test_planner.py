"""Tests for the iterative planner (MainAgent.plan_next_step and helpers)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.main_agent import (
    MainAgent,
    _validate_planner_decision,
)
from agents.registry import (
    EXECUTION_TARGETS,
    INVESTIGATION_TARGETS,
)
from graph.state import AgentState


@pytest.fixture
def mock_llm():
    """Create a mock LLM for testing."""
    llm = MagicMock()
    llm.ainvoke = AsyncMock()
    return llm


@pytest.fixture
def planner(mock_llm):
    """Create a MainAgent instance with mock LLM."""
    return MainAgent(mock_llm)


@pytest.fixture
def base_state():
    """Create a base agent state for planning tests."""
    return {
        "request": "Create a new channel called announcements",
        "guild_id": 123456789,
        "channel_id": 4001,
        "user_id": 2001,
        "user_permissions": {"administrator": True},
        "planning_iteration": 0,
        "completed_investigation_agents": [],
        "investigation_results": {},
        "draft_todos": [],
    }


# --- _validate_planner_decision tests ---


def test_validate_valid_need_investigation():
    # Arrange
    decision = {
        "status": "need_investigation",
        "investigation_targets": ["channel", "server"],
        "execution_candidates": [],
        "replace_todos": False,
        "summary": "Need to check existing channels first",
    }

    # Act
    result = _validate_planner_decision(decision)

    # Assert
    assert result["status"] == "need_investigation"
    assert result["investigation_targets"] == ["channel", "server"]
    assert result["replace_todos"] is False


def test_validate_valid_ready_for_approval():
    # Arrange
    decision = {
        "status": "ready_for_approval",
        "investigation_targets": [],
        "execution_candidates": [
            {"agent": "channel_execution", "action": "create", "params": {"name": "announcements"}},
        ],
        "replace_todos": True,
        "summary": "Ready to create the channel",
    }

    # Act
    result = _validate_planner_decision(decision)

    # Assert
    assert result["status"] == "ready_for_approval"


def test_validate_valid_done_no_execution():
    # Arrange
    decision = {
        "status": "done_no_execution",
        "investigation_targets": [],
        "execution_candidates": [],
        "summary": "Info only, nothing to execute",
    }

    # Act
    result = _validate_planner_decision(decision)

    # Assert
    assert result["status"] == "done_no_execution"


def test_validate_valid_error():
    # Arrange
    decision = {
        "status": "error",
        "summary": "Cannot fulfill request",
    }

    # Act
    result = _validate_planner_decision(decision)

    # Assert
    assert result["status"] == "error"


def test_validate_invalid_status_becomes_error():
    # Arrange
    decision = {"status": "invalid_status"}

    # Act
    result = _validate_planner_decision(decision)

    # Assert
    assert result["status"] == "error"


def test_validate_ready_for_approval_without_candidates_becomes_error():
    # Arrange
    decision = {
        "status": "ready_for_approval",
        "execution_candidates": [],
    }

    # Act
    result = _validate_planner_decision(decision)

    # Assert
    assert result["status"] == "error"
    assert "No execution candidates" in result["summary"]


def test_validate_need_investigation_without_targets_becomes_error():
    # Arrange
    decision = {
        "status": "need_investigation",
        "investigation_targets": [],
    }

    # Act
    result = _validate_planner_decision(decision)

    # Assert
    assert result["status"] == "error"
    assert "No investigation targets" in result["summary"]


def test_validate_non_list_targets_becomes_empty_list():
    # Arrange
    decision = {
        "status": "error",
        "investigation_targets": "not a list",
    }

    # Act
    result = _validate_planner_decision(decision)

    # Assert
    assert result["investigation_targets"] == []


def test_validate_non_bool_replace_becomes_false():
    # Arrange
    decision = {
        "status": "error",
        "replace_todos": "yes",
    }

    # Act
    result = _validate_planner_decision(decision)

    # Assert
    assert result["replace_todos"] is False


def test_validate_missing_fields_get_defaults():
    # Arrange
    decision = {"status": "error"}

    # Act
    result = _validate_planner_decision(decision)

    # Assert
    assert result["investigation_targets"] == []
    assert result["execution_candidates"] == []
    assert result["replace_todos"] is False
    assert result["summary"] == ""


# --- MainAgent.build_investigation_todos tests ---


def test_build_investigation_todos_filters_completed(planner):
    # Arrange
    targets = ["channel", "server", "role"]
    state: AgentState = {
        "completed_investigation_agents": ["channel_investigation"],
    }

    # Act
    todos = planner.build_investigation_todos(targets, state)

    # Assert
    assert len(todos) == 2
    agents = [t["agent"] for t in todos]
    assert "server_investigation" in agents
    assert "role_investigation" in agents
    assert "channel_investigation" not in agents


def test_build_investigation_todos_filters_invalid_targets(planner):
    # Arrange
    targets = ["channel", "nonexistent_agent"]
    state: AgentState = {"completed_investigation_agents": []}

    # Act
    todos = planner.build_investigation_todos(targets, state)

    # Assert
    assert len(todos) == 1
    assert todos[0]["agent"] == "channel_investigation"


def test_build_investigation_todos_empty_state(planner):
    # Arrange
    targets = ["channel"]
    state: AgentState = {}

    # Act
    todos = planner.build_investigation_todos(targets, state)

    # Assert
    assert len(todos) == 1
    assert todos[0] == {"agent": "channel_investigation", "action": "investigate", "params": {}}


# --- MainAgent.build_execution_todos tests ---


def test_build_execution_todos_valid(planner):
    # Arrange
    candidates = [
        {"agent": "channel_execution", "action": "create", "params": {"name": "general"}},
        {"agent": "role_execution", "action": "create", "params": {"name": "Moderator"}},
    ]

    # Act
    todos = planner.build_execution_todos(candidates)

    # Assert
    assert len(todos) == 2
    assert todos[0]["agent"] == "channel_execution"
    assert todos[0]["action"] == "create"
    assert todos[0]["params"] == {"name": "general"}


def test_build_execution_todos_filters_invalid_targets(planner):
    # Arrange
    candidates = [
        {"agent": "channel_execution", "action": "create", "params": {}},
        {"agent": "nonexistent_execution", "action": "do_thing", "params": {}},
    ]

    # Act
    todos = planner.build_execution_todos(candidates)

    # Assert
    assert len(todos) == 1
    assert todos[0]["agent"] == "channel_execution"


def test_build_execution_todos_filters_non_execution_suffix(planner):
    # Arrange
    candidates = [
        {"agent": "channel_investigation", "action": "investigate", "params": {}},
    ]

    # Act
    todos = planner.build_execution_todos(candidates)

    # Assert
    assert len(todos) == 0


def test_build_execution_todos_non_list_input(planner):
    # Arrange
    candidates = "not a list"

    # Act
    todos = planner.build_execution_todos(candidates)

    # Assert
    assert todos == []
    assert isinstance(todos, list)


# --- MainAgent.plan_next_step tests ---


@pytest.mark.asyncio
async def test_plan_next_step_need_investigation(planner, mock_llm, base_state):
    # Arrange
    mock_llm.ainvoke.return_value = MagicMock(
        content='{"status": "need_investigation", "investigation_targets": ["channel"], "execution_candidates": [], "replace_todos": false, "summary": "Need channel info"}'
    )

    # Act
    result = await planner.plan_next_step(base_state)

    # Assert
    assert result["status"] == "need_investigation"
    assert result["investigation_targets"] == ["channel"]
    assert result["summary"] == "Need channel info"


@pytest.mark.asyncio
async def test_plan_next_step_ready_for_approval(planner, mock_llm, base_state):
    # Arrange
    mock_llm.ainvoke.return_value = MagicMock(
        content='{"status": "ready_for_approval", "investigation_targets": [], "execution_candidates": [{"agent": "channel_execution", "action": "create", "params": {"name": "ann"}}], "replace_todos": true, "summary": "Ready"}'
    )

    # Act
    result = await planner.plan_next_step(base_state)

    # Assert
    assert result["status"] == "ready_for_approval"
    assert len(result["execution_candidates"]) == 1


@pytest.mark.asyncio
async def test_plan_next_step_done_no_execution(planner, mock_llm, base_state):
    # Arrange
    mock_llm.ainvoke.return_value = MagicMock(
        content='{"status": "done_no_execution", "investigation_targets": [], "execution_candidates": [], "summary": "Info only"}'
    )

    # Act
    result = await planner.plan_next_step(base_state)

    # Assert
    assert result["status"] == "done_no_execution"


@pytest.mark.asyncio
async def test_plan_next_step_includes_completed_agents(planner, mock_llm, base_state):
    # Arrange
    base_state["completed_investigation_agents"] = ["channel_investigation", "server_investigation"]
    base_state["investigation_results"] = {
        "investigation_channel": {"total_count": 5},
    }
    mock_llm.ainvoke.return_value = MagicMock(
        content='{"status": "ready_for_approval", "investigation_targets": [], "execution_candidates": [{"agent": "channel_execution", "action": "create", "params": {"name": "test"}}], "replace_todos": true, "summary": "Got it"}'
    )

    # Act
    result = await planner.plan_next_step(base_state)

    # Assert
    assert result["status"] == "ready_for_approval"
    # Verify the prompt included completed agents info
    call_args = mock_llm.ainvoke.call_args
    messages = call_args[0][0]
    human_content = messages[1].content
    assert "channel_investigation" in human_content
    assert "server_investigation" in human_content


@pytest.mark.asyncio
async def test_plan_next_step_includes_investigation_results(planner, mock_llm, base_state):
    # Arrange
    base_state["investigation_results"] = {
        "investigation_channel": {"total_count": 5, "text_channels": [{"name": "general"}]},
    }
    mock_llm.ainvoke.return_value = MagicMock(
        content='{"status": "done_no_execution", "investigation_targets": [], "execution_candidates": [], "summary": "Got results"}'
    )

    # Act
    result = await planner.plan_next_step(base_state)

    # Assert
    assert result["status"] == "done_no_execution"
    call_args = mock_llm.ainvoke.call_args
    messages = call_args[0][0]
    human_content = messages[1].content
    assert "investigation_channel" in human_content


@pytest.mark.asyncio
async def test_plan_next_step_malformed_json_returns_error(planner, mock_llm, base_state):
    # Arrange
    mock_llm.ainvoke.return_value = MagicMock(content="not json at all")

    # Act
    result = await planner.plan_next_step(base_state)

    # Assert
    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_plan_next_step_llm_exception_returns_error(planner, mock_llm, base_state):
    # Arrange
    mock_llm.ainvoke.side_effect = RuntimeError("API down")

    # Act
    result = await planner.plan_next_step(base_state)

    # Assert
    assert result["status"] == "error"
    assert "Planner error" in result["summary"]


@pytest.mark.asyncio
async def test_plan_next_step_json_with_codeblock(planner, mock_llm, base_state):
    # Arrange
    mock_llm.ainvoke.return_value = MagicMock(
        content='```json\n{"status": "done_no_execution", "investigation_targets": [], "execution_candidates": [], "summary": "Parsed from codeblock"}\n```'
    )

    # Act
    result = await planner.plan_next_step(base_state)

    # Assert
    assert result["status"] == "done_no_execution"
    assert result["summary"] == "Parsed from codeblock"


@pytest.mark.asyncio
async def test_plan_next_step_json_with_leading_text(planner, mock_llm, base_state):
    """LLMレスポンスにJSONの前にテキストがあってもパースできること。"""
    mock_llm.ainvoke.return_value = MagicMock(
        content='Here is my analysis:\n```json\n{"status": "done_no_execution", "investigation_targets": [], "execution_candidates": [], "summary": "Leading text handled"}\n```'
    )

    result = await planner.plan_next_step(base_state)

    assert result["status"] == "done_no_execution"
    assert result["summary"] == "Leading text handled"


@pytest.mark.asyncio
async def test_plan_next_step_json_codeblock_no_lang(planner, mock_llm, base_state):
    """言語指定なしの`````` コードブロックでもパースできること。"""
    mock_llm.ainvoke.return_value = MagicMock(
        content='```\n{"status": "done_no_execution", "investigation_targets": [], "execution_candidates": [], "summary": "No lang tag"}\n```'
    )

    result = await planner.plan_next_step(base_state)

    assert result["status"] == "done_no_execution"
    assert result["summary"] == "No lang tag"


@pytest.mark.asyncio
async def test_plan_next_step_json_wrapped_in_plain_prose(planner, mock_llm, base_state):
    """fenceなしの説明文に埋め込まれたJSONでもパースできること。"""
    mock_llm.ainvoke.return_value = MagicMock(
        content='After checking the request, the correct output is {"status": "done_no_execution", "investigation_targets": [], "execution_candidates": [], "summary": "Plain prose handled"}. End of response.'
    )

    result = await planner.plan_next_step(base_state)

    assert result["status"] == "done_no_execution"
    assert result["summary"] == "Plain prose handled"


# --- MainAgent.parse_request / build_todos backward compatibility ---


@pytest.mark.asyncio
async def test_parse_request_still_works(planner, mock_llm):
    # Arrange
    state: AgentState = {"request": "list all channels"}
    mock_llm.ainvoke.return_value = MagicMock(
        content='{"investigation_targets": ["channel"], "execution_candidates": []}'
    )

    # Act
    result = await planner.parse_request(state)

    # Assert
    assert result["investigation_targets"] == ["channel"]
    assert result["execution_candidates"] == []


def test_build_todos_still_works(planner):
    # Arrange
    parsed = {
        "investigation_targets": ["channel", "role"],
        "execution_candidates": [
            {"agent": "channel_execution", "action": "create", "params": {"name": "test"}},
        ],
    }

    # Act
    todos = planner.build_todos(parsed)

    # Assert
    assert len(todos) == 3
    assert todos[0] == {"agent": "channel_investigation", "action": "investigate", "params": {}}
    assert todos[2]["agent"] == "channel_execution"


@pytest.mark.asyncio
async def test_parse_request_empty_request(planner):
    # Arrange
    state: AgentState = {"request": ""}

    # Act
    result = await planner.parse_request(state)

    # Assert
    assert result == {"investigation_targets": [], "execution_candidates": [], "todos": []}
