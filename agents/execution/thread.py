import discord

from agents.base import MultiActionExecutionAgent
from graph.state import AgentState
from i18n import t


class ThreadExecutionAgent(MultiActionExecutionAgent):
    """スレッドの作成・編集・アーカイブ・ロック・メンバー管理を行うエージェント。"""

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "create": ["create_public_threads"],
        "edit": ["manage_threads"],
        "delete": ["manage_threads"],
        "add_member": ["manage_threads"],
        "join": [],
        "leave": [],
    }

    @property
    def name(self) -> str:
        return "thread_execution"

    async def _dispatch(self, action: str, params: dict, guild: discord.Guild) -> dict:
        handlers = {
            "create": self._create,
            "edit": self._edit,
            "delete": self._delete,
            "add_member": self._add_member,
            "join": self._join,
            "leave": self._leave,
        }
        handler = handlers.get(action)
        if not handler:
            return {"success": False, "action": action, "details": t("err.unknown_action", locale=self._locale, action=action)}
        return await handler(params, guild)

    async def _create(self, params: dict, guild: discord.Guild) -> dict:
        """スレッドを作成する。"""
        channel_id = params.get("channel_id")
        name = params.get("name")
        if not channel_id:
            return {"success": False, "action": "create", "details": t("exec.missing_param", locale=self._locale, param="channel_id")}
        if not name:
            return {"success": False, "action": "create", "details": t("exec.missing_param", locale=self._locale, param="name")}

        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "create", "details": t("not_found.channel", locale=self._locale, id=channel_id)}

        thread_type = discord.ChannelType.public_thread
        type_str = params.get("type", "public").lower()
        if type_str == "private":
            thread_type = discord.ChannelType.private_thread

        kwargs: dict = {"name": name, "type": thread_type}
        if "auto_archive_duration" in params:
            kwargs["auto_archive_duration"] = params["auto_archive_duration"]

        try:
            thread = await channel.create_thread(**kwargs)
            return {"success": True, "action": "create", "details": t("exec.thread.created", locale=self._locale, name=thread.name, id=thread.id)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "create", "details": str(e)}

    async def _edit(self, params: dict, guild: discord.Guild) -> dict:
        """スレッドを編集する。"""
        thread_id = params.get("thread_id")
        if not thread_id:
            return {"success": False, "action": "edit", "details": t("exec.missing_param", locale=self._locale, param="thread_id")}

        thread = guild.get_thread(thread_id)
        if not thread:
            thread = await self._find_thread(guild, thread_id)
        if not thread:
            return {"success": False, "action": "edit", "details": t("not_found.thread", locale=self._locale, id=thread_id)}

        kwargs: dict = {}
        if "name" in params:
            kwargs["name"] = params["name"]
        if "archived" in params:
            kwargs["archived"] = params["archived"]
        if "locked" in params:
            kwargs["locked"] = params["locked"]
        if "slowmode" in params:
            kwargs["slowmode_delay"] = params["slowmode"]

        if not kwargs:
            return {"success": False, "action": "edit", "details": t("exec.no_editable_params", locale=self._locale)}

        try:
            await thread.edit(**kwargs)
            return {"success": True, "action": "edit", "details": t("exec.thread.edited", locale=self._locale, name=thread.name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit", "details": str(e)}

    async def _delete(self, params: dict, guild: discord.Guild) -> dict:
        """スレッドを削除する。"""
        thread_id = params.get("thread_id")
        if not thread_id:
            return {"success": False, "action": "delete", "details": t("exec.missing_param", locale=self._locale, param="thread_id")}

        thread = guild.get_thread(thread_id)
        if not thread:
            thread = await self._find_thread(guild, thread_id)
        if not thread:
            return {"success": False, "action": "delete", "details": t("not_found.thread", locale=self._locale, id=thread_id)}

        thread_name = thread.name
        try:
            await thread.delete()
            return {"success": True, "action": "delete", "details": t("exec.thread.deleted", locale=self._locale, name=thread_name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "delete", "details": str(e)}

    async def _add_member(self, params: dict, guild: discord.Guild) -> dict:
        """メンバーをスレッドに追加する。"""
        thread_id = params.get("thread_id")
        member_id = params.get("member_id")
        if not thread_id:
            return {"success": False, "action": "add_member", "details": t("exec.missing_param", locale=self._locale, param="thread_id")}
        if not member_id:
            return {"success": False, "action": "add_member", "details": t("exec.missing_param", locale=self._locale, param="member_id")}

        thread = guild.get_thread(thread_id)
        if not thread:
            thread = await self._find_thread(guild, thread_id)
        if not thread:
            return {"success": False, "action": "add_member", "details": t("not_found.thread", locale=self._locale, id=thread_id)}

        member = guild.get_member(member_id)
        if not member:
            return {"success": False, "action": "add_member", "details": t("not_found.member", locale=self._locale, id=member_id)}

        try:
            await thread.add_member(member)
            return {"success": True, "action": "add_member", "details": t("exec.thread.member_added", locale=self._locale, member=member.display_name, name=thread.name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "add_member", "details": str(e)}

    async def _join(self, params: dict, guild: discord.Guild) -> dict:
        """ボットをスレッドに参加させる。"""
        thread_id = params.get("thread_id")
        if not thread_id:
            return {"success": False, "action": "join", "details": t("exec.missing_param", locale=self._locale, param="thread_id")}

        thread = guild.get_thread(thread_id)
        if not thread:
            thread = await self._find_thread(guild, thread_id)
        if not thread:
            return {"success": False, "action": "join", "details": t("not_found.thread", locale=self._locale, id=thread_id)}

        try:
            await thread.join()
            return {"success": True, "action": "join", "details": t("exec.thread.joined", locale=self._locale, name=thread.name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "join", "details": str(e)}

    async def _leave(self, params: dict, guild: discord.Guild) -> dict:
        """ボットをスレッドから退出させる。"""
        thread_id = params.get("thread_id")
        if not thread_id:
            return {"success": False, "action": "leave", "details": t("exec.missing_param", locale=self._locale, param="thread_id")}

        thread = guild.get_thread(thread_id)
        if not thread:
            thread = await self._find_thread(guild, thread_id)
        if not thread:
            return {"success": False, "action": "leave", "details": t("not_found.thread", locale=self._locale, id=thread_id)}

        try:
            await thread.leave()
            return {"success": True, "action": "leave", "details": t("exec.thread.left", locale=self._locale, name=thread.name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "leave", "details": str(e)}

    async def _find_thread(self, guild: discord.Guild, thread_id: int) -> discord.Thread | None:
        """サーバー内のアクティブスレッドからIDで検索する。"""
        for channel in guild.text_channels:
            for thread in channel.threads:
                if thread.id == thread_id:
                    return thread
        return None
