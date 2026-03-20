"""Tests for the agent registry and capability metadata."""
import pytest

from agents.base import ExecutionAgent, _find_action, InvestigationAgent
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
