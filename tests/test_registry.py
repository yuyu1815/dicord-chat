"""Tests for the agent registry and capability metadata."""
import pytest
from unittest.mock import MagicMock, AsyncMock

import discord

from agents.base import (
    ExecutionAgent,
    MultiActionExecutionAgent,
    SingleActionExecutionAgent,
    _find_action,
    InvestigationAgent,
)
from agents.registry import (
    EXECUTION_TARGETS,
    INVESTIGATION_TARGETS,
    get_execution_agent_names,
    get_single_action_agent_names,
    get_single_action_agents,
    load_agent_module,
)
from graph.state import AgentState


# --- _find_action helper tests ---


def test_find_action_returns_first_match():
    """最初のマッチするtodoのアクション名を返すこと。"""
    state: AgentState = {
        "todos": [
            {"agent": "emoji_execution", "action": "create", "params": {"name": "a"}},
            {"agent": "emoji_execution", "action": "delete", "params": {"name": "b"}},
        ],
    }
    assert _find_action(state, "emoji_execution") == "create"


def test_find_action_skips_blocked():
    """_blocked=True のtodoはスキップされること。"""
    state: AgentState = {
        "todos": [
            {"agent": "emoji_execution", "action": "create", "params": {}, "_blocked": True},
            {"agent": "emoji_execution", "action": "delete", "params": {}},
        ],
    }
    assert _find_action(state, "emoji_execution") == "delete"


def test_find_action_returns_none_when_no_match():
    """マッチするtodoがない場合はNoneを返すこと。"""
    state: AgentState = {"todos": []}
    assert _find_action(state, "emoji_execution") is None


def test_find_action_ignores_other_agents():
    """別のエージェントのtodoは無視されること。"""
    state: AgentState = {
        "todos": [
            {"agent": "channel_execution", "action": "create", "params": {}},
        ],
    }
    assert _find_action(state, "emoji_execution") is None


def test_find_action_all_blocked_returns_none():
    """全todoがブロックされている場合はNoneを返すこと。"""
    state: AgentState = {
        "todos": [
            {"agent": "emoji_execution", "action": "create", "params": {}, "_blocked": True},
            {"agent": "emoji_execution", "action": "delete", "params": {}, "_blocked": True},
        ],
    }
    assert _find_action(state, "emoji_execution") is None


# --- ExecutionAgent.single_action capability tests ---


def test_execution_agent_default_single_action_is_false():
    """ExecutionAgentのデフォルトのsingle_actionがFalseであること。"""
    assert ExecutionAgent.single_action is False


class _SingleActionStub(ExecutionAgent):
    single_action: bool = True

    @property
    def name(self) -> str:
        return "single_stub"

    async def execute(self, state: AgentState, guild):
        return {"success": True}


class _MultiActionStub(ExecutionAgent):
    single_action: bool = False

    @property
    def name(self) -> str:
        return "multi_stub"

    async def execute(self, state: AgentState, guild):
        return {"success": True}


def test_single_action_agent_capability():
    """single_action=Trueが設定できること。"""
    assert _SingleActionStub.single_action is True


def test_multi_action_agent_capability():
    """single_action=Falseが設定できること。"""
    assert _MultiActionStub.single_action is False


# --- SingleActionExecutionAgent tests ---


class _SingleActionTemplate(SingleActionExecutionAgent):
    """テスト用のSingleActionExecutionAgent具象サブクラス。"""

    ACTION_HANDLERS = {"greet": "Greet user"}

    @property
    def name(self) -> str:
        return "test_single"

    async def _do_greet(self, guild, params: dict) -> dict:
        return {"success": True, "action": "greet", "details": f"Hello {params.get('who', 'world')}"}


def test_single_action_template_is_single_action():
    """SingleActionExecutionAgentサブクラスのsingle_actionがTrueであること。"""
    assert _SingleActionTemplate.single_action is True


@pytest.mark.asyncio
async def test_single_action_template_execute():
    """SingleActionExecutionAgent.executeが_do_メソッドに正しくディスパッチすること。"""
    agent = _SingleActionTemplate()
    state: AgentState = {
        "todos": [{"agent": "test_single", "action": "greet", "params": {"who": "Alice"}}],
    }
    result = await agent.execute(state, MagicMock())
    assert result["success"] is True
    assert "Hello Alice" in result["details"]


@pytest.mark.asyncio
async def test_single_action_template_no_todo():
    """マッチするtodoがない場合に失敗を返すこと。"""
    agent = _SingleActionTemplate()
    state: AgentState = {"todos": []}
    result = await agent.execute(state, MagicMock())
    assert result["success"] is False


@pytest.mark.asyncio
async def test_single_action_template_unknown_action():
    """未知のアクションに対してUnknown actionエラーを返すこと。"""
    agent = _SingleActionTemplate()
    state: AgentState = {
        "todos": [{"agent": "test_single", "action": "unknown_action", "params": {}}],
    }
    result = await agent.execute(state, MagicMock())
    assert result["success"] is False
    assert "Unknown action" in result["details"]


@pytest.mark.asyncio
async def test_single_action_template_forbidden_error():
    """discord.Forbidden時にMissing permissionsを返すこと。"""
    agent = _SingleActionTemplate()
    state: AgentState = {
        "todos": [{"agent": "test_single", "action": "greet", "params": {}}],
    }

    async def _raise_forbidden(guild, params):
        raise discord.Forbidden(MagicMock(), "nope")

    agent._do_greet = _raise_forbidden
    result = await agent.execute(state, MagicMock())
    assert result["success"] is False
    assert "Missing permissions" in result["details"]


@pytest.mark.asyncio
async def test_single_action_template_not_found_error():
    """discord.NotFound時にnot_found_messageを返すこと。"""
    agent = _SingleActionTemplate()
    agent.not_found_message = "Custom not found."
    state: AgentState = {
        "todos": [{"agent": "test_single", "action": "greet", "params": {}}],
    }

    async def _raise_not_found(guild, params):
        raise discord.NotFound(MagicMock(), "not found")

    agent._do_greet = _raise_not_found
    result = await agent.execute(state, MagicMock())
    assert result["success"] is False
    assert result["details"] == "Custom not found."


@pytest.mark.asyncio
async def test_single_action_template_skips_blocked_todo():
    """_blocked=Trueのtodoを_find_actionがスキップして次のtodoを処理すること。

    注: ExecutionAgent.run()が事前にblocked todoをフィルタリングするため、
    execute()に渡されるstateにはblocked todoが含まれない。
    このテストでは_find_actionがblocked todoを正しくスキップすることを検証する。
    """
    agent = _SingleActionTemplate()
    # _find_action skips blocked, so action_name resolves to the second todo's action
    state: AgentState = {
        "todos": [
            {"agent": "test_single", "action": "greet", "params": {}, "_blocked": True},
            {"agent": "test_single", "action": "greet", "params": {"who": "Bob"}},
        ],
    }
    # Verify _find_action correctly skips blocked
    assert _find_action(state, "test_single") == "greet"
    # In production, ExecutionAgent.run() would filter out blocked todos
    # before calling execute(). We test execute() with a pre-filtered state:
    filtered_state: AgentState = {
        "todos": [{"agent": "test_single", "action": "greet", "params": {"who": "Bob"}}],
    }
    result = await agent.execute(filtered_state, MagicMock())
    assert result["success"] is True
    assert "Hello Bob" in result["details"]


# --- MultiActionExecutionAgent tests ---


class _MultiActionTemplate(MultiActionExecutionAgent):
    """テスト用のMultiActionExecutionAgent具象サブクラス。"""

    @property
    def name(self) -> str:
        return "test_multi"

    async def _dispatch(self, action: str, params: dict, guild) -> dict:
        handlers = {"do_a": self._handler_a, "do_b": self._handler_b}
        handler = handlers.get(action)
        if not handler:
            return {"success": False, "action": action, "details": f"Unknown action: {action}"}
        return await handler(params, guild)

    async def _handler_a(self, params: dict, guild) -> dict:
        return {"success": True, "action": "do_a", "details": "did A"}

    async def _handler_b(self, params: dict, guild) -> dict:
        return {"success": True, "action": "do_b", "details": "did B"}


def test_multi_action_template_is_not_single_action():
    """MultiActionExecutionAgentサブクラスのsingle_actionがFalseであること。"""
    assert _MultiActionTemplate.single_action is False


@pytest.mark.asyncio
async def test_multi_action_template_execute_single():
    """単一todoを正しく処理すること。"""
    agent = _MultiActionTemplate()
    state: AgentState = {
        "todos": [{"agent": "test_multi", "action": "do_a", "params": {}}],
    }
    result = await agent.execute(state, MagicMock())
    assert result["success"] is True
    assert "did A" in result["details"]


@pytest.mark.asyncio
async def test_multi_action_template_execute_multiple():
    """複数todoを全て処理し集計すること。"""
    agent = _MultiActionTemplate()
    state: AgentState = {
        "todos": [
            {"agent": "test_multi", "action": "do_a", "params": {}},
            {"agent": "test_multi", "action": "do_b", "params": {}},
        ],
    }
    result = await agent.execute(state, MagicMock())
    assert result["success"] is True
    assert "did A" in result["details"]
    assert "did B" in result["details"]


@pytest.mark.asyncio
async def test_multi_action_template_execute_partial_failure():
    """一部のアクションが失敗した場合にsuccess=Falseを返すこと。"""
    agent = _MultiActionTemplate()
    state: AgentState = {
        "todos": [
            {"agent": "test_multi", "action": "do_a", "params": {}},
            {"agent": "test_multi", "action": "unknown", "params": {}},
        ],
    }
    result = await agent.execute(state, MagicMock())
    assert result["success"] is False


@pytest.mark.asyncio
async def test_multi_action_template_skips_blocked():
    """_blocked=Trueのtodoをスキップすること。"""
    agent = _MultiActionTemplate()
    state: AgentState = {
        "todos": [
            {"agent": "test_multi", "action": "do_a", "params": {}, "_blocked": True},
            {"agent": "test_multi", "action": "do_b", "params": {}},
        ],
    }
    result = await agent.execute(state, MagicMock())
    assert result["success"] is True
    assert "did B" in result["details"]
    assert "did A" not in result["details"]


@pytest.mark.asyncio
async def test_multi_action_template_no_todos():
    """マッチするtodoがない場合に失敗を返すこと。"""
    agent = _MultiActionTemplate()
    state: AgentState = {"todos": []}
    result = await agent.execute(state, MagicMock())
    assert result["success"] is False
    assert "No matching" in result["details"]


# --- Inheritance hierarchy tests ---


def test_single_action_is_subclass_of_execution():
    """SingleActionExecutionAgentがExecutionAgentのサブクラスであること。"""
    assert issubclass(SingleActionExecutionAgent, ExecutionAgent)


def test_multi_action_is_subclass_of_execution():
    """MultiActionExecutionAgentがExecutionAgentのサブクラスであること。"""
    assert issubclass(MultiActionExecutionAgent, ExecutionAgent)


def test_real_single_action_agents_use_template():
    """実際の単一アクションエージェントがSingleActionExecutionAgentを使用していること。"""
    from agents.execution.emoji import EmojiExecutionAgent
    from agents.execution.sticker import StickerExecutionAgent
    from agents.execution.soundboard import SoundboardExecutionAgent
    for cls in (EmojiExecutionAgent, StickerExecutionAgent, SoundboardExecutionAgent):
        assert issubclass(cls, SingleActionExecutionAgent), f"{cls.__name__} should inherit SingleActionExecutionAgent"


def test_real_multi_action_agents_use_template():
    """実際の複数アクションエージェントがMultiActionExecutionAgentを使用していること。"""
    from agents.execution.channel import ChannelExecutionAgent
    from agents.execution.role import RoleExecutionAgent
    from agents.execution.server import ServerExecutionAgent
    for cls in (ChannelExecutionAgent, RoleExecutionAgent, ServerExecutionAgent):
        assert issubclass(cls, MultiActionExecutionAgent), f"{cls.__name__} should inherit MultiActionExecutionAgent"


# --- get_single_action_agents tests ---


def test_get_single_action_agents_returns_frozenset():
    """get_single_action_agentsがfrozensetを返すこと。"""
    result = get_single_action_agents()
    assert isinstance(result, frozenset)


def test_get_single_action_agents_includes_known_single_action_agents():
    """既知の単一アクションエージェントが全て含まれること。"""
    expected = {
        "automod_execution",
        "event_execution",
        "stage_execution",
        "webhook_execution",
        "invite_execution",
        "emoji_execution",
        "sticker_execution",
        "soundboard_execution",
    }
    result = get_single_action_agents()
    assert expected.issubset(result), (
        f"Missing agents: {expected - result}"
    )


def test_get_single_action_agents_excludes_multi_action_agents():
    """複数アクションエージェントが含まれないこと。"""
    multi_action = {
        "channel_execution",
        "category_execution",
        "thread_execution",
        "forum_execution",
        "role_execution",
        "message_execution",
        "member_execution",
        "server_execution",
        "permission_execution",
        "vc_execution",
    }
    result = get_single_action_agents()
    assert not (multi_action & result), (
        f"Multi-action agents incorrectly included: {multi_action & result}"
    )


# --- load_agent_module tests ---


def test_load_agent_module_returns_instance_for_valid_target():
    """有効なtargetに対してエージェントインスタンスを返すこと。"""
    agent = load_agent_module("channel", "execution")
    assert agent is not None
    assert agent.name == "channel_execution"


def test_load_agent_module_returns_none_for_invalid_target():
    """無効なtargetに対してNoneを返すこと。"""
    agent = load_agent_module("nonexistent_agent_xyz", "execution")
    assert agent is None


def test_load_agent_module_investigation():
    """調査エージェントを正しくロードできること。"""
    agent = load_agent_module("channel", "investigation")
    assert agent is not None
    assert agent.name == "channel_investigation"


# --- Backward compatibility tests ---


def test_cog_agent_cog_alias_exists():
    """cogs.agent_cog._load_agent_moduleがエイリアスとして存在すること。"""
    from cogs.agent_cog import _load_agent_module
    assert callable(_load_agent_module)


def test_cog_alias_returns_same_result():
    """エイリアスが元の関数と同じ結果を返すこと。"""
    from cogs.agent_cog import _load_agent_module as cog_loader
    from agents.registry import load_agent_module as registry_loader

    agent1 = cog_loader("channel", "execution")
    agent2 = registry_loader("channel", "execution")
    assert agent1 is not None
    assert agent2 is not None
    assert agent1.name == agent2.name


# --- Canonical target list tests ---


def test_investigation_targets_is_nonempty():
    """INVESTIGATION_TARGETSが空でないこと。"""
    assert len(INVESTIGATION_TARGETS) > 0


def test_execution_targets_is_nonempty():
    """EXECUTION_TARGETSが空でないこと。"""
    assert len(EXECUTION_TARGETS) > 0


def test_execution_targets_subset_of_investigation():
    """全実行ターゲットが調査ターゲットのサブセットであること。"""
    assert set(EXECUTION_TARGETS).issubset(set(INVESTIGATION_TARGETS))


def test_investigation_targets_match_disk_modules():
    """INVESTIGATION_TARGETSがagents.investigation下のモジュールに対応すること。"""
    import importlib
    import pkgutil
    pkg = importlib.import_module("agents.investigation")
    disk_names = {
        name for _, name, _ in pkgutil.iter_modules(pkg.__path__)
    }
    assert set(INVESTIGATION_TARGETS) == disk_names, (
        f"Mismatch: on disk={disk_names - set(INVESTIGATION_TARGETS)}, "
        f"in list but not on disk={set(INVESTIGATION_TARGETS) - disk_names}"
    )


def test_execution_targets_match_disk_modules():
    """EXECUTION_TARGETSがagents.execution下のモジュールに対応すること。"""
    import importlib
    import pkgutil
    pkg = importlib.import_module("agents.execution")
    disk_names = {
        name for _, name, _ in pkgutil.iter_modules(pkg.__path__)
    }
    assert set(EXECUTION_TARGETS) == disk_names, (
        f"Mismatch: on disk={disk_names - set(EXECUTION_TARGETS)}, "
        f"in list but not on disk={set(EXECUTION_TARGETS) - disk_names}"
    )


def test_get_execution_agent_names_format():
    """get_execution_agent_namesが各ターゲットに_executionを付与して返すこと。"""
    names = get_execution_agent_names()
    for target in EXECUTION_TARGETS:
        assert f"{target}_execution" in names
    assert len(names) == len(EXECUTION_TARGETS)


def test_get_single_action_agent_names_is_frozenset():
    """get_single_action_agent_namesがfrozensetを返すこと。"""
    result = get_single_action_agent_names()
    assert isinstance(result, frozenset)


def test_get_single_action_agent_names_is_subset_of_all():
    """単一アクションエージェントが全実行エージェントのサブセットであること。"""
    single = get_single_action_agent_names()
    all_agents = set(get_execution_agent_names())
    assert single.issubset(all_agents)


def test_main_agent_imports_from_registry():
    """main_agentがレジストリからターゲットをインポートしていること。"""
    import agents.main_agent as ma
    assert ma.INVESTIGATION_TARGETS is INVESTIGATION_TARGETS
    assert ma.EXECUTION_TARGETS is EXECUTION_TARGETS


# --- classify_agent_kind tests ---


def test_classify_agent_kind_investigation():
    """調査エージェント名からinvestigationが判定されること。"""
    from graph.state import classify_agent_kind
    assert classify_agent_kind("channel_investigation") == "investigation"
    assert classify_agent_kind("server_investigation") == "investigation"


def test_classify_agent_kind_execution():
    """実行エージェント名からexecutionが判定されること。"""
    from graph.state import classify_agent_kind
    assert classify_agent_kind("channel_execution") == "execution"
    assert classify_agent_kind("emoji_execution") == "execution"


def test_classify_agent_kind_unknown():
    """未知のサフィックスの場合はNoneが返ること。"""
    from graph.state import classify_agent_kind
    assert classify_agent_kind("unknown_module") is None
    assert classify_agent_kind("") is None
    assert classify_agent_kind("investigation_channel") is None


# --- agent_target_from_name tests ---


def test_agent_target_from_name_investigation():
    """調査エージェント名からターゲットが取り出されること。"""
    from graph.state import agent_target_from_name
    assert agent_target_from_name("channel_investigation") == "channel"
    assert agent_target_from_name("audit_log_investigation") == "audit_log"


def test_agent_target_from_name_execution():
    """実行エージェント名からターゲットが取り出されること。"""
    from graph.state import agent_target_from_name
    assert agent_target_from_name("channel_execution") == "channel"
    assert agent_target_from_name("emoji_execution") == "emoji"


def test_agent_target_from_name_no_suffix():
    """サフィックスがない場合はそのまま返ること。"""
    from graph.state import agent_target_from_name
    assert agent_target_from_name("channel") == "channel"
    assert agent_target_from_name("") == ""


# --- Todo type and is_execution_todo / is_investigation_todo tests ---


def test_todo_is_a_typeddict():
    """TodoがTypedDictのサブクラスであること。"""
    from graph.state import Todo
    from typing_extensions import is_typeddict
    assert is_typeddict(Todo)


def test_is_execution_todo_true():
    """実行todoに対してTrueが返ること。"""
    from graph.state import is_execution_todo
    assert is_execution_todo({"agent": "channel_execution", "action": "create", "params": {}}) is True


def test_is_execution_todo_false_for_investigation():
    """調査todoに対してFalseが返ること。"""
    from graph.state import is_execution_todo
    assert is_execution_todo({"agent": "channel_investigation", "action": "investigate", "params": {}}) is False


def test_is_execution_todo_handles_empty_agent():
    """agentが空文字のtodoは実行扱いになること。"""
    from graph.state import is_execution_todo
    assert is_execution_todo({"agent": "", "action": "x", "params": {}}) is True


def test_is_investigation_todo_true():
    """調査todoに対してTrueが返ること。"""
    from graph.state import is_investigation_todo
    assert is_investigation_todo({"agent": "channel_investigation", "action": "investigate", "params": {}}) is True


def test_is_investigation_todo_false_for_execution():
    """実行todoに対してFalseが返ること。"""
    from graph.state import is_investigation_todo
    assert is_investigation_todo({"agent": "channel_execution", "action": "create", "params": {}}) is False


# --- Planner status constants tests ---


def test_planner_status_constants_are_strings():
    """プランナーステータス定数が文字列であること。"""
    from graph.state import (
        PLANNER_STATUS_DONE_NO_EXECUTION,
        PLANNER_STATUS_ERROR,
        PLANNER_STATUS_NEED_INVESTIGATION,
        PLANNER_STATUS_READY_FOR_APPROVAL,
    )
    assert PLANNER_STATUS_NEED_INVESTIGATION == "need_investigation"
    assert PLANNER_STATUS_READY_FOR_APPROVAL == "ready_for_approval"
    assert PLANNER_STATUS_DONE_NO_EXECUTION == "done_no_execution"
    assert PLANNER_STATUS_ERROR == "error"


def test_valid_planner_statuses_contains_all():
    """VALID_PLANNER_STATUSESが全てのステータス定数を含むこと。"""
    from graph.state import (
        VALID_PLANNER_STATUSES,
        PLANNER_STATUS_DONE_NO_EXECUTION,
        PLANNER_STATUS_ERROR,
        PLANNER_STATUS_NEED_INVESTIGATION,
        PLANNER_STATUS_READY_FOR_APPROVAL,
    )
    assert isinstance(VALID_PLANNER_STATUSES, frozenset)
    assert VALID_PLANNER_STATUSES == {
        PLANNER_STATUS_NEED_INVESTIGATION,
        PLANNER_STATUS_READY_FOR_APPROVAL,
        PLANNER_STATUS_DONE_NO_EXECUTION,
        PLANNER_STATUS_ERROR,
    }


def test_agent_state_todo_fields_use_todo_type():
    """AgentStateのtodo関連フィールドがTodo型を使用していること。"""
    from graph.state import AgentState, Todo
    import typing
    hints = typing.get_type_hints(AgentState)
    for field in ("todos", "pending_investigation_todos", "draft_todos", "proposed_todos"):
        hint = hints.get(field)
        assert hint is not None, f"Field {field} missing from AgentState hints"
        # Verify it's a list of Todo (not list[dict])
        origin = typing.get_origin(hint)
        args = typing.get_args(hint)
        assert origin is list, f"Field {field} expected list origin, got {origin}"
        assert args[0] is Todo, f"Field {field} expected Todo arg, got {args[0]}"
