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
from i18n import t, get_locale_from_ctx

logger = logging.getLogger("discord_bot")

APPROVAL_TIMEOUT = 300

# Backward-compatible aliases for existing tests and external references.
_load_agent_module = load_agent_module
_compute_todos_hash = compute_todos_hash
_format_final_response = format_final_response
_format_results = format_results
_format_execution_candidates = format_execution_candidates
_split_message = split_message


def _get_db_path(bot: commands.Bot) -> str:
    return bot.config.get("database_url", "database/bot.db").replace("sqlite:///", "")


async def _save_history(
    db_path: str,
    *,
    user_id: int,
    guild_id: int,
    session_id: str,
    request: str,
    response: str,
) -> None:
    from database.conversation import save_conversation_turn
    try:
        await save_conversation_turn(
            db_path,
            user_id=user_id,
            guild_id=guild_id,
            session_id=session_id,
            request=request,
            response=response,
        )
    except Exception as e:
        logger.error("Failed to save conversation history: %s", e)


class ApprovalView(discord.ui.View):
    """承認フローのDiscord UIビュー。"""

    def __init__(self, bot: commands.Bot, approval_id: str, state: AgentState) -> None:
        super().__init__(timeout=APPROVAL_TIMEOUT)
        self.bot = bot
        self.approval_id = approval_id
        self.state = state
        locale = state.get("locale", "en")
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.label == "Approve":
                    child.label = t("ui.approval_approve", locale=locale)
                elif child.label == "Reject":
                    child.label = t("ui.approval_reject", locale=locale)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """リクエスト元ユーザーのみが承認/拒否できる。"""
        if interaction.user.id != self.state["user_id"]:
            locale = self.state.get("locale", "en")
            await interaction.response.send_message(
                t("ui.approval_only_requester", locale=locale), ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """承認ボタン。実行を開始する。"""
        self.approved = True
        await self._save_approval(True)
        locale = self.state.get("locale", "en")
        await interaction.response.send_message(t("ui.approval_executing", locale=locale), ephemeral=True)
        self.stop()
        asyncio.create_task(self._execute_approved())

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """拒否ボタン。操作をキャンセルする。"""
        await self._save_approval(False)
        locale = self.state.get("locale", "en")
        await interaction.response.send_message(t("ui.approval_cancelled", locale=locale), ephemeral=True)
        self.stop()
        asyncio.create_task(self._handle_rejected())

    async def _save_approval(self, approved: bool) -> None:
        """承認結果をデータベースに保存する。"""
        proposed_todos = self.state.get("proposed_todos", [])
        todos_hash = compute_todos_hash(proposed_todos)
        db_path = _get_db_path(self.bot)
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
        db_path = _get_db_path(self.bot)
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
                locale = self.state.get("locale", "en")
                await channel.send(
                    t("ui.approval_verification_failed", locale=locale),
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

        # Save conversation history
        db_path = _get_db_path(self.bot)
        await _save_history(
            db_path,
            user_id=self.state["user_id"],
            guild_id=self.state["guild_id"],
            session_id=self.approval_id,
            request=self.state.get("request", ""),
            response=formatted,
        )

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

        locale = self.state.get("locale", "en")
        final_response = final_state.get("final_response", t("cog.request_cancelled", locale=locale))
        for chunk in split_message(final_response, max_length=1900):
            await channel.send(chunk)

        # Save conversation history
        db_path = _get_db_path(self.bot)
        await _save_history(
            db_path,
            user_id=self.state["user_id"],
            guild_id=self.state["guild_id"],
            session_id=self.approval_id,
            request=self.state.get("request", ""),
            response=final_response,
        )


class AgentCog(commands.Cog):
    """ユーザーリクエストを処理し、エージェントをオーケストレーションするメインCog。"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="manage", description="Manage Discord server via AI agents")
    async def manage(self, ctx: commands.Context, *, request: str) -> None:
        """エントリーポイント。ワークフローを実行し、調査結果・承認・実行を行う。"""
        if not ctx.guild:
            locale = get_locale_from_ctx(ctx)
            await ctx.send(t("cog.requires_server", locale=locale))
            return

        locale = get_locale_from_ctx(ctx)
        await ctx.defer()

        perms = ctx.author.guild_permissions
        user_permissions = {name: value for name, value in perms}

        db_path = _get_db_path(self.bot)

        # Load conversation history
        from database.conversation import load_conversation_history
        try:
            history = await load_conversation_history(
                db_path, user_id=ctx.author.id, guild_id=ctx.guild.id,
            )
        except Exception:
            history = []

        state: AgentState = {
            "request": request,
            "guild_id": ctx.guild.id,
            "channel_id": ctx.channel.id,
            "user_id": ctx.author.id,
            "user_permissions": user_permissions,
            "approval_id": str(uuid.uuid4()),
            "locale": locale,
            "conversation_history": history,
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
            error_msg = error or t("cog.error_planning", locale=locale)
            for chunk in split_message(f"{t('cog.error_prefix', locale=locale)}{error_msg}", max_length=1900):
                await ctx.send(chunk)
            await _save_history(
                db_path, user_id=ctx.author.id, guild_id=ctx.guild.id,
                session_id=state["approval_id"],
                request=request, response=error_msg,
            )
            return

        if plan_status == "done_no_execution":
            investigation_text = format_results(
                final_state.get("investigation_results", {}),
                title=t("cog.investigation_results", locale=locale),
            )
            final_response = final_state.get("final_response", t("cog.investigation_complete", locale=locale))
            response_parts = [t("cog.request_header", locale=locale, request=request)]
            if investigation_text:
                response_parts.append(investigation_text)
            response_parts.append(final_response)
            full_response = "\n".join(response_parts)
            for chunk in split_message(full_response, max_length=1900):
                await ctx.send(chunk)
            await _save_history(
                db_path, user_id=ctx.author.id, guild_id=ctx.guild.id,
                session_id=state["approval_id"],
                request=request, response=full_response,
            )
            return

        # レスポンスを構築
        investigation_text = format_results(
            final_state.get("investigation_results", {}),
            title=t("cog.investigation_results", locale=locale),
        )
        execution_text = format_execution_candidates(final_state.get("todos", []), locale=locale)

        response_parts = [t("cog.request_header", locale=locale, request=request)]
        if investigation_text:
            response_parts.append(investigation_text)
        if execution_text:
            response_parts.append(execution_text)
        else:
            response_parts.append("\n" + t("cog.no_candidates", locale=locale))

        full_response = "\n".join(response_parts)

        if approval_required:
            view = ApprovalView(self.bot, final_state["approval_id"], final_state)
            chunks = split_message(full_response, max_length=1900)
            for chunk in chunks:
                await ctx.send(chunk, view=view if chunk == chunks[-1] else None)
        else:
            for chunk in split_message(full_response, max_length=1900):
                await ctx.send(chunk)
            await _save_history(
                db_path, user_id=ctx.author.id, guild_id=ctx.guild.id,
                session_id=state["approval_id"],
                request=request, response=full_response,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AgentCog(bot))
