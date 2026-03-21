"""エージェントの動的ローダーとキャパビリティレジストリ。

エージェントモジュールを名前で動的にインポートし、インスタンスを返す。
ワーキングセットは ``cogs.agent_cog`` や ``graph.workflow`` で
遅延インポートされるため、Cogとワークフロー間の結合が排除される。

このモジュールは調査・実行対象の正典リスト（single source of truth）も提供する。
"""
import importlib
import logging
import pkgutil
from typing import Any

from agents.base import (
    BaseAgent,
    ExecutionAgent,
    InvestigationAgent,
    MultiActionExecutionAgent,
    SingleActionExecutionAgent,
)

logger = logging.getLogger("discord_bot")

# ---------------------------------------------------------------------------
# Canonical target lists -- single source of truth
# ---------------------------------------------------------------------------

INVESTIGATION_TARGETS: list[str] = [
    "server", "channel", "category", "thread", "forum",
    "message", "role", "permission", "member", "vc",
    "stage", "event", "automod", "invite", "webhook",
    "emoji", "sticker", "soundboard", "audit_log", "poll",
    "search", "url_scraper",
]

EXECUTION_TARGETS: list[str] = [
    "server", "channel", "category", "thread", "forum",
    "message", "role", "permission", "member", "vc",
    "stage", "event", "automod", "invite", "webhook",
    "emoji", "sticker", "soundboard", "poll",
]


def get_execution_agent_names() -> list[str]:
    """実行エージェント名の正典リストを返す（例: ``"channel_execution"``）。

    Returns:
        ``EXECUTION_TARGETS`` の各要素に ``"_execution"`` を付与したリスト。
    """
    return [f"{t}_execution" for t in EXECUTION_TARGETS]


def get_single_action_agent_names() -> frozenset[str]:
    """単一アクション実行エージェント名のフロzensetを返す。

    :func:`get_single_action_agents` のエイリアス。
    """
    return get_single_action_agents()


def load_agent_module(target: str, kind: str) -> BaseAgent | None:
    """エージェントモジュールを動的インポートし、クラスインスタンスを返す。

    Args:
        target: エージェントの対象名（例: ``"channel"``）。
        kind: ``"investigation"`` または ``"execution"``。

    Returns:
        エージェントインスタンス。読み込み失敗時は ``None``。
    """
    try:
        if kind == "investigation":
            module_path = f"agents.investigation.{target}"
            class_suffix = "InvestigationAgent"
        else:
            module_path = f"agents.execution.{target}"
            class_suffix = "ExecutionAgent"

        module = __import__(module_path, fromlist=[None])
        for attr in vars(module).values():
            if (
                isinstance(attr, type)
                and attr.__name__.endswith(class_suffix)
                and issubclass(attr, BaseAgent)
                and attr is not BaseAgent
                and attr is not InvestigationAgent
                and attr is not ExecutionAgent
                and attr is not MultiActionExecutionAgent
                and attr is not SingleActionExecutionAgent
            ):
                return attr()
    except (ImportError, AttributeError) as e:
        logger.warning("Could not load agent %s/%s: %s", kind, target, e)
    return None


def get_single_action_agents() -> frozenset[str]:
    """全実行エージェントをスキャンし、 ``single_action=True`` のものを返す。

    各エージェントモジュールをインポートして ``ExecutionAgent`` サブクラスを探し、
    クラス属性 ``single_action`` が ``True`` であればその ``name`` を収集する。
    インポートに失敗したモジュールは無視する。

    Returns:
        単一アクションエージェントの ``name`` フロzenset。
    """
    agents: set[str] = set()
    package = importlib.import_module("agents.execution")
    for importer, modname, _ in pkgutil.walk_packages(
        package.__path__, prefix="agents.execution.",
    ):
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue
        for attr in vars(mod).values():
            if (
                isinstance(attr, type)
                and issubclass(attr, ExecutionAgent)
                and attr is not ExecutionAgent
                and getattr(attr, "single_action", False)
            ):
                # name is a property; instantiate to get it
                try:
                    agents.add(attr().name)
                except Exception:
                    pass
    return frozenset(agents)
