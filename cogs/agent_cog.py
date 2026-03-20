import asyncio
import logging
import uuid
from typing import Any

import aiosqlite
import discord
from discord.ext import commands

from agents.base import BaseAgent, ExecutionAgent, InvestigationAgent
from agents.main_agent import MainAgent
from graph.state import AgentState

logger = logging.getLogger("discord_bot")

APPROVAL_TIMEOUT = 300


def _load_agent_module(target: str, kind: str) -> BaseAgent | None:
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
            ):
                return attr()
    except (ImportError, AttributeError) as e:
        logger.warning("Could not load agent %s/%s: %s", kind, target, e)
    return None


class ApprovalView(discord.ui.View):
    """承認フローのDiscord UIビュー。"""

    def __init__(self, bot: commands.Bot, approval_id: str, state: AgentState) -> None:
        super().__init__(timeout=APPROVAL_TIMEOUT)
        self.bot = bot
        self.approval_id = approval_id
        self.state = state

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """リクエスト元ユーザーのみが承認/拒否できる。"""
        if interaction.user.id != self.state["user_id"]:
            await interaction.response.send_message("Only the requester can approve.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """承認ボタン。実行を開始する。"""
        self.approved = True
        await self._save_approval(True)
        await interaction.response.send_message("Executing...", ephemeral=True)
        self.stop()
        asyncio.create_task(self._execute_approved())

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """拒否ボタン。操作をキャンセルする。"""
        await self._save_approval(False)
        await interaction.response.send_message("Operation cancelled.", ephemeral=True)
        self.stop()

    async def _save_approval(self, approved: bool) -> None:
        """承認結果をデータベースに保存する。"""
        db_path = self.bot.config.get("database_url", "database/bot.db").replace("sqlite:///", "")
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO approvals (id, approved, user_id, created_at) VALUES (?, ?, ?, datetime('now'))",
                (self.approval_id, approved, self.state["user_id"]),
            )
            await db.commit()

    async def _execute_approved(self) -> None:
        """承認後に実行エージェントを実行し、結果をチャンネルに送信する。"""
        guild = self.bot.get_guild(self.state["guild_id"])
        if not guild:
            logger.error("Guild %s not found", self.state["guild_id"])
            return

        self.state["approved"] = True
        results = await _run_agents(self.state, guild, execution_only=True)

        channel = guild.get_channel(self.state["channel_id"])
        if not channel or not isinstance(channel, discord.TextChannel):
            return

        formatted = _format_results(results, title="Execution Results")
        for chunk in _split_message(formatted, max_length=1900):
            await channel.send(chunk)


class AgentCog(commands.Cog):
    """ユーザーリクエストを処理し、エージェントをオーケストレーションするメインCog。"""

    def __init__(self, bot: commands.Bot, main_agent: MainAgent) -> None:
        self.bot = bot
        self.main_agent = main_agent

    @commands.hybrid_command(name="manage", description="Manage Discord server via AI agents")
    async def manage(self, ctx: commands.Context, *, request: str) -> None:
        """エントリーポイント。リクエストを解析し、調査→実行候補を提示する。"""
        if not ctx.guild:
            await ctx.send("This command requires a server context.")
            return

        await ctx.defer()

        perms = ctx.author.guild_permissions
        user_permissions = {name: value for name, value in perms}

        state: AgentState = {
            "request": request,
            "guild_id": ctx.guild.id,
            "channel_id": ctx.channel.id,
            "user_id": ctx.author.id,
            "user_permissions": user_permissions,
            "todos": [],
            "investigation_results": {},
            "approval_id": str(uuid.uuid4()),
            "approved": False,
            "execution_results": {},
            "final_response": "",
            "error": None,
        }

        parsed = await self.main_agent.parse_request(state)
        state["todos"] = self.main_agent.build_todos(parsed)

        if not state["todos"]:
            await ctx.send("Could not determine any actions for that request.")
            return

        investigation_results = await _run_agents(state, ctx.guild, investigation_only=True)
        state["investigation_results"] = investigation_results

        investigation_text = _format_results(investigation_results, title="Investigation Results")
        execution_text = _format_execution_candidates(state["todos"])

        response_parts = [f"**Request:** {request}\n"]
        if investigation_text:
            response_parts.append(investigation_text)
        if execution_text:
            response_parts.append(execution_text)
        else:
            response_parts.append("\nNo execution candidates. Investigation complete.")

        full_response = "\n".join(response_parts)

        execution_todos = [t for t in state["todos"] if "investigation" not in t.get("agent", "")]
        if execution_todos:
            view = ApprovalView(self.bot, state["approval_id"], state)
            for chunk in _split_message(full_response, max_length=1900):
                await ctx.send(chunk, view=view if chunk == _split_message(full_response, max_length=1900)[-1] else None)
        else:
            for chunk in _split_message(full_response, max_length=1900):
                await ctx.send(chunk)


async def _run_agents(
    state: AgentState,
    guild: discord.Guild,
    investigation_only: bool = False,
    execution_only: bool = False,
) -> dict[str, Any]:
    """タスクリストに基づいて該当エージェントを実行する。

    Args:
        state: ワークフロー状態。
        guild: 対象サーバー。
        investigation_only: 調査エージェントのみ実行。
        execution_only: 実行エージェントのみ実行。

    Returns:
        エージェント名をキーとした結果の辞書。
    """
    results: dict[str, Any] = {}
    todos = state.get("todos", [])

    for todo in todos:
        agent_name = todo.get("agent", "")
        kind = "investigation" if "investigation" in agent_name else "execution"

        if investigation_only and kind != "investigation":
            continue
        if execution_only and kind != "execution":
            continue

        target = agent_name.replace(f"_{kind}", "")
        agent = _load_agent_module(target, kind)

        if not agent:
            continue

        try:
            new_state = await agent.run(state, guild)
            key = f"{kind}_{target}"
            if kind == "investigation":
                results[key] = new_state.get("investigation_results", {}).get(agent.name, {})
            else:
                results[key] = new_state.get("execution_results", {}).get(agent.name, {})
        except Exception as e:
            logger.error("Agent %s failed: %s", agent_name, e)
            results[f"{kind}_{target}"] = {"error": str(e)}

    return results


def _format_results(results: dict[str, Any], title: str) -> str:
    """調査/実行結果をDiscord向けにフォーマットする。

    Args:
        results: エージェントの実行結果。
        title: セクションタイトル。

    Returns:
        フォーマットされた文字列。
    """
    if not results:
        return ""

    lines = [f"**{title}**\n"]
    for key, value in results.items():
        if isinstance(value, dict) and "error" in value:
            lines.append(f"- {key}: ERROR - {value['error']}")
            continue
        lines.append(f"- {key}:")
        if isinstance(value, list):
            for item in value[:10]:
                lines.append(f"  - {item}")
            if len(value) > 10:
                lines.append(f"  - ... and {len(value) - 10} more")
        elif isinstance(value, dict):
            denied = value.get("permission_denied", [])
            if denied:
                for d in denied:
                    lines.append(f"  - :x: {d['action']}: {d['message']}")
            for k, v in value.items():
                if k == "permission_denied":
                    continue
                text = str(v)
                if len(text) > 100:
                    text = text[:100] + "..."
                lines.append(f"  - {k}: {text}")

    return "\n".join(lines)


def _format_execution_candidates(todos: list[dict[str, Any]]) -> str:
    """ユーザー確認用の実行候補リストをフォーマットする。

    Args:
        todos: 全タスクリスト。

    Returns:
        フォーマットされた文字列。
    """
    execution_todos = [t for t in todos if "investigation" not in t.get("agent", "")]
    if not execution_todos:
        return ""

    lines = ["**Pending Execution (requires approval):**\n"]
    for i, todo in enumerate(execution_todos, 1):
        action = todo.get("action", "unknown")
        params = todo.get("params", {})
        agent = todo.get("agent", "unknown")
        param_str = ", ".join(f"{k}={v}" for k, v in params.items())
        lines.append(f"{i}. [{agent}] {action}({param_str})")

    return "\n".join(lines)


def _split_message(text: str, max_length: int = 1900) -> list[str]:
    """Discordのメッセージ上限に合わせてテキストを分割する。

    Args:
        text: 分割対象の文字列。
        max_length: チャンクの最大長。

    Returns:
        分割された文字列のリスト。
    """
    if len(text) <= max_length:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, max_length)
        if split_at == -1:
            split_at = max_length
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AgentCog(bot, main_agent))
