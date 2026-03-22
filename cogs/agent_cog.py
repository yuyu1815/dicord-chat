import asyncio
import logging
import uuid
from typing import Any

import aiosqlite
import discord
from discord.ext import commands

from agents.registry import load_agent_module
from graph.state import (
    AgentState,
    TodoProgress,
    TodoStatus,
    agent_target_from_name,
)
from database.conversation import load_conversation_history, save_conversation_turn
from formatters.response import (
    compute_todos_hash,
    format_execution_candidates,
    format_final_response,
    format_progress_plan,
    format_results,
    format_thread_progress_event,
    split_message,
)
from graph.workflow import build_post_approval_workflow, build_pre_approval_workflow
from i18n import t, get_locale_from_ctx

logger = logging.getLogger("discord_bot")

APPROVAL_TIMEOUT = 300


def _update_all_todo_progress(
    state: AgentState, status: TodoStatus,
) -> None:
    """Update all items in state's todo_progress to the given status."""
    for tp in state.get("todo_progress", []):
        tp["status"] = status

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
        asyncio.create_task(self._execute_approved_safe())

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
        except Exception:
            logger.exception("Failed to verify approval %s", self.approval_id)
            return False

    async def _execute_approved_safe(self) -> None:
        """Wrapper around _execute_approved that catches unexpected errors."""
        try:
            await self._execute_approved()
        except Exception as e:
            logger.exception("Unexpected error during approved execution")
            guild = self.bot.get_guild(self.state.get("guild_id", 0))
            if guild:
                channel = guild.get_channel(self.state["channel_id"]) or guild.get_thread(self.state["channel_id"])
                if channel and isinstance(channel, (discord.TextChannel, discord.Thread)):
                    locale = self.state.get("locale", "en")
                    await channel.send(
                        t("cog.error_prefix", locale=locale) + str(e),
                    )

    async def _execute_approved(self) -> None:
        """承認後にpost-approvalワークフローを再開し、結果をチャンネルに送信する。"""
        guild = self.bot.get_guild(self.state["guild_id"])
        if not guild:
            logger.error("Guild %s not found", self.state["guild_id"])
            return

        # Verify persisted approval record matches the current proposed_todos.
        if not await self._verify_approval():
            channel = guild.get_channel(self.state["channel_id"]) or guild.get_thread(self.state["channel_id"])
            if channel and isinstance(channel, (discord.TextChannel, discord.Thread)):
                locale = self.state.get("locale", "en")
                await channel.send(
                    t("ui.approval_verification_failed", locale=locale),
                )
            return

        self.state["approved"] = True
        self.state["approval_status"] = "approved"

        # Update todo_progress to approved
        _update_all_todo_progress(self.state, "approved")

        # Run execution with progress callbacks.
        final_state = await self._run_with_progress()

        channel = guild.get_channel(self.state["channel_id"]) or guild.get_thread(self.state["channel_id"])
        if not channel or not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return

        # Update plan message with final status.
        await self._update_plan_message(final_state)

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

    async def _run_with_progress(self) -> AgentState:
        """Run agents sequentially, posting progress events to thread.

        Each todo is matched to its ``TodoProgress`` entry by ``todo_id``
        (stored in the todo via ``_todo_id`` injection) so that even
        multiple todos for the same agent are tracked independently.

        Deduplication is by ``todo_id`` only (cycle prevention).  The same
        agent can run for multiple distinct todos.

        State from the previous agent's result is merged into
        ``current_state`` before the next agent runs, ensuring
        inter-agent state continuity.
        """
        state = self.state
        bot = state.get("bot")
        guild = bot.get_guild(state.get("guild_id")) if bot else None
        locale = state.get("locale", "en")

        proposed_todos = state.get("proposed_todos", [])
        execution_todos = [
            t for t in proposed_todos if "investigation" not in t.get("agent", "")
        ]

        # Build todo_id -> TodoProgress lookup for per-todo tracking.
        tp_by_id: dict[str, TodoProgress] = {}
        for tp in state.get("todo_progress", []):
            tp_by_id[tp["todo_id"]] = tp

        progress_events: list[dict[str, Any]] = list(state.get("progress_events", []))

        results: dict[str, Any] = {}
        seen_todo_ids: set[str] = set()
        current_state: dict[str, Any] = dict(state)

        for todo in execution_todos:
            agent_name = todo.get("agent", "")
            todo_id = todo.get("_todo_id", "")
            tp = tp_by_id.get(todo_id)

            # Skip only if the exact same todo_id was already processed
            # (cycle prevention). Allow multiple todos for the same agent.
            if todo_id and todo_id in seen_todo_ids:
                if tp:
                    tp["status"] = "skipped"
                continue
            if todo_id:
                seen_todo_ids.add(todo_id)

            # Mark in_progress
            if tp:
                tp["status"] = "in_progress"
            label = tp.get("label", agent_name) if tp else agent_name

            start_event: dict[str, Any] = {
                "type": "start",
                "agent": agent_name,
                "label": label,
            }
            progress_events.append(start_event)
            await self._post_thread_event(start_event, locale)

            # Execute agent — carry over state from previous agent runs.
            current_state["todos"] = execution_todos
            current_state["approved"] = True

            result_key = agent_name
            try:
                target = agent_target_from_name(agent_name)
                agent_module = load_agent_module(target, "execution")
                if not agent_module:
                    raise RuntimeError(f"Agent {agent_name} not available")
                if not guild:
                    raise RuntimeError("Guild not found")

                new_state = await agent_module.run(current_state, guild)
                result_key = agent_module.name
                results[result_key] = new_state.get("execution_results", {}).get(result_key, {})

                # Merge agent return state into current_state for next agent.
                for k, v in new_state.items():
                    if k not in ("approved", "todos"):
                        current_state[k] = v

                if tp:
                    tp["status"] = "completed"

                success_event: dict[str, Any] = {
                    "type": "success",
                    "agent": agent_name,
                    "label": label,
                }
                progress_events.append(success_event)
                await self._post_thread_event(success_event, locale)

            except Exception as e:
                logger.exception("Execution agent %s failed", agent_name)
                results[result_key] = {"error": str(e)}

                if tp:
                    tp["status"] = "failed"

                error_event: dict[str, Any] = {
                    "type": "error",
                    "agent": agent_name,
                    "label": label,
                    "detail": str(e),
                }
                progress_events.append(error_event)
                await self._post_thread_event(error_event, locale)

        # Single plan message refresh after all agents are done (reduces API calls).
        todo_progress = list(tp_by_id.values())
        await self._refresh_plan_message(todo_progress, locale)

        # Build final state.
        merged_results = dict(state.get("execution_results", {}))
        merged_results.update(results)

        final: AgentState = dict(current_state)
        final["execution_results"] = merged_results

        # Set plan_status based on results
        has_failure = any(
            isinstance(v, dict) and "error" in v
            for v in results.values()
        )
        final["plan_status"] = "completed_with_errors" if has_failure else "completed"

        final["progress_events"] = progress_events
        final["todo_progress"] = todo_progress

        # final_response is left empty; format_final_response() will
        # render execution_results (and any investigation_summary from
        # the agent return) from the state itself.
        final["final_response"] = ""

        return final

    async def _refresh_plan_message(
        self, todo_progress: list[TodoProgress], locale: str,
    ) -> None:
        """Update the plan message with current todo progress."""
        plan_msg_id = self.state.get("progress_plan_message_id")
        if not plan_msg_id:
            return

        guild = self.bot.get_guild(self.state["guild_id"])
        if not guild:
            return
        channel = guild.get_channel(self.state["channel_id"]) or guild.get_thread(self.state["channel_id"])
        if not channel or not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return

        try:
            msg = await channel.fetch_message(plan_msg_id)
            body = format_progress_plan(
                self.state.get("request", ""),
                todo_progress,
                locale=locale,
            )
            chunks = split_message(body, max_length=1900)
            # Only update the first chunk (plan message); keep it concise.
            await msg.edit(content=chunks[0])
        except Exception as e:
            logger.warning("Failed to refresh plan message %s: %s", plan_msg_id, e)

    async def _post_thread_event(self, event: dict[str, Any], locale: str) -> None:
        """Post a progress event to the progress thread."""
        thread_id = self.state.get("progress_thread_id")
        if not thread_id:
            return
        guild = self.bot.get_guild(self.state["guild_id"])
        if not guild:
            return
        thread = guild.get_thread(thread_id)
        if not thread:
            return
        try:
            text = format_thread_progress_event(event, locale=locale)
            await thread.send(text)
        except Exception as e:
            logger.warning("Failed to post thread event: %s", e)

    async def _update_plan_message(self, final_state: AgentState) -> None:
        """Final update of the plan message with completed status."""
        todo_progress = final_state.get("todo_progress", list(self.state.get("todo_progress", [])))
        locale = self.state.get("locale", "en")
        await self._refresh_plan_message(todo_progress, locale)

    async def _handle_rejected(self) -> None:
        """拒否時に終了メッセージをチャンネルに送信する。"""
        guild = self.bot.get_guild(self.state["guild_id"])
        if not guild:
            return

        self.state["approval_status"] = "rejected"

        post_workflow = build_post_approval_workflow()
        app = post_workflow.compile()
        final_state = await app.ainvoke(self.state)

        channel = guild.get_channel(self.state["channel_id"]) or guild.get_thread(self.state["channel_id"])
        if not channel or not isinstance(channel, (discord.TextChannel, discord.Thread)):
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

    async def handle_manage(self, ctx: commands.Context, *, request: str) -> None:
        """エントリーポイント。ワークフローを実行し、調査結果・承認・実行を行う。"""
        if not ctx.guild:
            locale = get_locale_from_ctx(ctx)
            await ctx.send(t("cog.requires_server", locale=locale))
            return

        locale = get_locale_from_ctx(ctx)
        if ctx.interaction:
            await ctx.defer()

        perms = ctx.author.guild_permissions
        user_permissions = {name: value for name, value in perms}

        db_path = _get_db_path(self.bot)

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
            # Inject _todo_id into proposed_todos so _run_with_progress()
            # can match each todo to its TodoProgress entry.
            todo_progress = final_state.get("todo_progress", [])
            for todo, tp in zip(final_state.get("proposed_todos", []), todo_progress):
                todo["_todo_id"] = tp["todo_id"]

            view = ApprovalView(self.bot, final_state["approval_id"], final_state)
            chunks = split_message(full_response, max_length=1900)
            plan_message = None
            for i, chunk in enumerate(chunks):
                is_first = (i == 0)
                is_last = (i == len(chunks) - 1)
                plan_message = await ctx.send(
                    chunk, view=view if is_last else None,
                )
                if is_first and plan_message:
                    final_state["progress_plan_message_id"] = plan_message.id

            # Create progress thread from the last chunk message
            thread = None
            if plan_message:
                try:
                    max_request_len = 80 - len(t("progress.thread_name", locale=locale, request=""))
                    thread_name = t(
                        "progress.thread_name", locale=locale,
                        request=request[:max(1, max_request_len)],
                    )
                    thread = await plan_message.create_thread(
                        name=thread_name, auto_archive_duration=1440,
                    )
                    final_state["progress_thread_id"] = thread.id

                    # Post investigation summary as the first thread message
                    inv_summary = final_state.get("investigation_summary", "")
                    if inv_summary:
                        for part in split_message(inv_summary, max_length=1900):
                            await thread.send(part)
                except Exception as e:
                    logger.warning("Failed to create progress thread: %s", e)
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
