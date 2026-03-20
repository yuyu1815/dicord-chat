import asyncio
import logging
import uuid

import aiosqlite
import discord
from discord.ext import commands

from agents.base import BaseAgent, ExecutionAgent, InvestigationAgent
from agents.registry import load_agent_module
from formatters.response import (
    compute_todos_hash,
    format_execution_candidates,
    format_final_response,
    format_results,
    split_message,
)
from graph.state import AgentState

logger = logging.getLogger("discord_bot")

APPROVAL_TIMEOUT = 300

# Backward-compatible aliases for existing tests and external references.
_load_agent_module = load_agent_module
_compute_todos_hash = compute_todos_hash
_format_final_response = format_final_response
_format_results = format_results
_format_execution_candidates = format_execution_candidates
_split_message = split_message


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
        asyncio.create_task(self._handle_rejected())

    async def _save_approval(self, approved: bool) -> None:
        """承認結果をデータベースに保存する。"""
        proposed_todos = self.state.get("proposed_todos", [])
        todos_hash = compute_todos_hash(proposed_todos)
        db_path = self.bot.config.get("database_url", "database/bot.db").replace("sqlite:///", "")
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO approvals (id, approved, user_id, created_at, todos_hash) VALUES (?, ?, ?, datetime('now'), ?)",
                (self.approval_id, approved, self.state["user_id"], todos_hash),
            )
            await db.commit()

    async def _verify_approval(self) -> bool:
        """保存された承認レコードを現在のproposed_todosと照合する。

        ハッシュが一致しない場合は改ざんの可能性があるためFalseを返す。
        レコードが存在しない場合もFalseを返す。

        Returns:
            照合成功時は ``True``。
        """
        current_hash = compute_todos_hash(self.state.get("proposed_todos", []))
        db_path = self.bot.config.get("database_url", "database/bot.db").replace("sqlite:///", "")
        try:
            async with aiosqlite.connect(db_path) as db:
                cursor = await db.execute(
                    "SELECT approved, todos_hash FROM approvals WHERE id = ?",
                    (self.approval_id,),
                )
                row = await cursor.fetchone()
                if row is None:
                    logger.error("Approval record %s not found in database", self.approval_id)
                    return False
                db_approved, db_hash = row
                if not db_approved:
                    logger.warning("Approval %s is not approved in database", self.approval_id)
                    return False
                if db_hash and db_hash != current_hash:
                    logger.error(
                        "Todos hash mismatch for approval %s: db=%s, current=%s",
                        self.approval_id, db_hash, current_hash,
                    )
                    return False
                return True
        except Exception as e:
            logger.error("Failed to verify approval %s: %s", self.approval_id, e)
            return False

    async def _execute_approved(self) -> None:
        """承認後にpost-approvalワークフローを再開し、結果をチャンネルに送信する。"""
        from graph.workflow import build_post_approval_workflow

        guild = self.bot.get_guild(self.state["guild_id"])
        if not guild:
            logger.error("Guild %s not found", self.state["guild_id"])
            return

        # Verify persisted approval record matches the current proposed_todos.
        if not await self._verify_approval():
            channel = guild.get_channel(self.state["channel_id"])
            if channel and isinstance(channel, discord.TextChannel):
                await channel.send(
                    "Approval verification failed: proposed todos may have been "
                    "tampered with. Execution aborted for safety.",
                )
            return

        self.state["approved"] = True
        self.state["approval_status"] = "approved"

        post_workflow = build_post_approval_workflow()
        app = post_workflow.compile()
        final_state = await app.ainvoke(self.state)

        channel = guild.get_channel(self.state["channel_id"])
        if not channel or not isinstance(channel, discord.TextChannel):
            return

        formatted = format_final_response(final_state)
        for chunk in split_message(formatted, max_length=1900):
            await channel.send(chunk)

    async def _handle_rejected(self) -> None:
        """拒否時に終了メッセージをチャンネルに送信する。"""
        from graph.workflow import build_post_approval_workflow

        guild = self.bot.get_guild(self.state["guild_id"])
        if not guild:
            return

        self.state["approval_status"] = "rejected"

        post_workflow = build_post_approval_workflow()
        app = post_workflow.compile()
        final_state = await app.ainvoke(self.state)

        channel = guild.get_channel(self.state["channel_id"])
        if not channel or not isinstance(channel, discord.TextChannel):
            return

        final_response = final_state.get("final_response", "Request cancelled.")
        for chunk in split_message(final_response, max_length=1900):
            await channel.send(chunk)


class AgentCog(commands.Cog):
    """ユーザーリクエストを処理し、エージェントをオーケストレーションするメインCog。"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="manage", description="Manage Discord server via AI agents")
    async def manage(self, ctx: commands.Context, *, request: str) -> None:
        """エントリーポイント。ワークフローを実行し、調査結果・承認・実行を行う。"""
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
            "approval_id": str(uuid.uuid4()),
            "bot": self.bot,
        }

        from graph.workflow import build_pre_approval_workflow

        pre_workflow = build_pre_approval_workflow()
        app = pre_workflow.compile()
        final_state = await app.ainvoke(state)

        plan_status = final_state.get("plan_status", "")
        approval_required = final_state.get("approval_required", False)
        error = final_state.get("error")

        if plan_status == "error":
            error_msg = error or "An error occurred during planning."
            for chunk in split_message(f"**Error:** {error_msg}", max_length=1900):
                await ctx.send(chunk)
            return

        if plan_status == "done_no_execution":
            investigation_text = format_results(
                final_state.get("investigation_results", {}),
                title="Investigation Results",
            )
            final_response = final_state.get("final_response", "Investigation complete.")
            response_parts = [f"**Request:** {request}\n"]
            if investigation_text:
                response_parts.append(investigation_text)
            response_parts.append(final_response)
            full_response = "\n".join(response_parts)
            for chunk in split_message(full_response, max_length=1900):
                await ctx.send(chunk)
            return

        # レスポンスを構築
        investigation_text = format_results(
            final_state.get("investigation_results", {}),
            title="Investigation Results",
        )
        execution_text = format_execution_candidates(final_state.get("todos", []))

        response_parts = [f"**Request:** {request}\n"]
        if investigation_text:
            response_parts.append(investigation_text)
        if execution_text:
            response_parts.append(execution_text)
        else:
            response_parts.append("\nNo execution candidates. Investigation complete.")

        full_response = "\n".join(response_parts)

        if approval_required:
            view = ApprovalView(self.bot, final_state["approval_id"], final_state)
            chunks = split_message(full_response, max_length=1900)
            for chunk in chunks:
                await ctx.send(chunk, view=view if chunk == chunks[-1] else None)
        else:
            for chunk in split_message(full_response, max_length=1900):
                await ctx.send(chunk)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AgentCog(bot))
