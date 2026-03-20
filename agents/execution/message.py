import discord

from agents.base import MultiActionExecutionAgent
from graph.state import AgentState
from i18n import t


class MessageExecutionAgent(MultiActionExecutionAgent):
    """メッセージの送信・編集・削除・ピン留め・リアクション操作を行うエージェント。"""

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "send": ["send_messages"],
        "edit": ["manage_messages"],
        "delete": ["manage_messages"],
        "pin": ["manage_messages"],
        "unpin": ["manage_messages"],
        "add_reaction": ["add_reactions"],
        "remove_reaction": ["manage_messages"],
        "clear_reactions": ["manage_messages"],
        "bulk_delete": ["manage_messages"],
    }

    @property
    def name(self) -> str:
        return "message_execution"

    async def _dispatch(self, action: str, params: dict, guild: discord.Guild) -> dict:
        handlers = {
            "send": self._send,
            "edit": self._edit,
            "delete": self._delete,
            "pin": self._pin,
            "unpin": self._unpin,
            "add_reaction": self._add_reaction,
            "remove_reaction": self._remove_reaction,
            "clear_reactions": self._clear_reactions,
            "bulk_delete": self._bulk_delete,
        }
        handler = handlers.get(action)
        if not handler:
            return {"success": False, "action": action, "details": t("err.unknown_action", locale=self._locale, action=action)}
        return await handler(params, guild)

    async def _send(self, params: dict, guild: discord.Guild) -> dict:
        """メッセージを送信する。"""
        channel_id = params.get("channel_id")
        content = params.get("content", "")
        if not channel_id:
            return {"success": False, "action": "send", "details": t("exec.missing_param", locale=self._locale, param="channel_id")}

        channel = guild.get_channel(channel_id)
        if not channel or not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
            return {"success": False, "action": "send", "details": t("not_found.sendable_channel", locale=self._locale, id=channel_id)}

        embed_data = params.get("embed")
        embed = None
        if embed_data:
            embed = discord.Embed.from_dict(embed_data) if isinstance(embed_data, dict) else None

        files = []
        raw_files = params.get("files", [])
        for file_info in raw_files:
            if isinstance(file_info, str):
                files.append(discord.File(file_info))
            elif isinstance(file_info, dict):
                files.append(discord.File(file_info["path"], filename=file_info.get("filename")))

        try:
            message = await channel.send(content=content, embed=embed, files=files)
            return {"success": True, "action": "send", "details": t("exec.message.sent", locale=self._locale, channel=channel.name, id=message.id)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "send", "details": str(e)}

    async def _edit(self, params: dict, guild: discord.Guild) -> dict:
        """メッセージを編集する。"""
        message_id = params.get("message_id")
        content = params.get("content")
        if not message_id:
            return {"success": False, "action": "edit", "details": t("exec.missing_param", locale=self._locale, param="message_id")}
        if not content:
            return {"success": False, "action": "edit", "details": t("exec.missing_param", locale=self._locale, param="content")}

        try:
            message = await self._find_message(guild, message_id)
            if not message:
                return {"success": False, "action": "edit", "details": t("not_found.message", locale=self._locale, id=message_id)}
            await message.edit(content=content)
            return {"success": True, "action": "edit", "details": t("exec.message.edited", locale=self._locale, id=message_id)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit", "details": str(e)}

    async def _delete(self, params: dict, guild: discord.Guild) -> dict:
        """メッセージを削除する。"""
        message_id = params.get("message_id")
        if not message_id:
            return {"success": False, "action": "delete", "details": t("exec.missing_param", locale=self._locale, param="message_id")}

        try:
            message = await self._find_message(guild, message_id)
            if not message:
                return {"success": False, "action": "delete", "details": t("not_found.message", locale=self._locale, id=message_id)}
            await message.delete()
            return {"success": True, "action": "delete", "details": t("exec.message.deleted", locale=self._locale, id=message_id)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "delete", "details": str(e)}

    async def _pin(self, params: dict, guild: discord.Guild) -> dict:
        """メッセージをピン留めする。"""
        channel_id = params.get("channel_id")
        message_id = params.get("message_id")
        if not channel_id or not message_id:
            return {"success": False, "action": "pin", "details": t("exec.message.missing_multi_param", locale=self._locale, param1="channel_id", param2="message_id")}

        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "pin", "details": t("not_found.channel", locale=self._locale, id=channel_id)}

        try:
            message = await channel.fetch_message(message_id)
            await message.pin()
            return {"success": True, "action": "pin", "details": t("exec.message.pinned", locale=self._locale, id=message_id, channel=channel.name)}
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
            return {"success": False, "action": "pin", "details": str(e)}

    async def _unpin(self, params: dict, guild: discord.Guild) -> dict:
        """メッセージのピン留めを解除する。"""
        channel_id = params.get("channel_id")
        message_id = params.get("message_id")
        if not channel_id or not message_id:
            return {"success": False, "action": "unpin", "details": t("exec.message.missing_multi_param", locale=self._locale, param1="channel_id", param2="message_id")}

        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "unpin", "details": t("not_found.channel", locale=self._locale, id=channel_id)}

        try:
            message = await channel.fetch_message(message_id)
            await message.unpin()
            return {"success": True, "action": "unpin", "details": t("exec.message.unpinned", locale=self._locale, id=message_id, channel=channel.name)}
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
            return {"success": False, "action": "unpin", "details": str(e)}

    async def _add_reaction(self, params: dict, guild: discord.Guild) -> dict:
        """メッセージにリアクションを追加する。"""
        channel_id = params.get("channel_id")
        message_id = params.get("message_id")
        emoji = params.get("emoji")
        if not channel_id or not message_id or not emoji:
            return {"success": False, "action": "add_reaction", "details": t("exec.message.missing_required", locale=self._locale, params="channel_id, message_id, emoji")}

        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "add_reaction", "details": t("not_found.channel", locale=self._locale, id=channel_id)}

        try:
            message = await channel.fetch_message(message_id)
            await message.add_reaction(emoji)
            return {"success": True, "action": "add_reaction", "details": t("exec.message.reaction_added", locale=self._locale, emoji=emoji, id=message_id)}
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
            return {"success": False, "action": "add_reaction", "details": str(e)}

    async def _remove_reaction(self, params: dict, guild: discord.Guild) -> dict:
        """メッセージのリアクションを削除する。"""
        channel_id = params.get("channel_id")
        message_id = params.get("message_id")
        emoji = params.get("emoji")
        member_id = params.get("member_id")
        if not channel_id or not message_id or not emoji:
            return {"success": False, "action": "remove_reaction", "details": t("exec.message.missing_required", locale=self._locale, params="channel_id, message_id, emoji")}

        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "remove_reaction", "details": t("not_found.channel", locale=self._locale, id=channel_id)}

        try:
            message = await channel.fetch_message(message_id)
            if member_id:
                member = guild.get_member(member_id)
                if member:
                    await message.remove_reaction(emoji, member)
                else:
                    return {"success": False, "action": "remove_reaction", "details": t("not_found.member", locale=self._locale, id=member_id)}
            else:
                await message.remove_reaction(emoji, guild.me)
            return {"success": True, "action": "remove_reaction", "details": t("exec.message.reaction_removed", locale=self._locale, emoji=emoji, id=message_id)}
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
            return {"success": False, "action": "remove_reaction", "details": str(e)}

    async def _clear_reactions(self, params: dict, guild: discord.Guild) -> dict:
        """メッセージの全リアクションを削除する。"""
        channel_id = params.get("channel_id")
        message_id = params.get("message_id")
        if not channel_id or not message_id:
            return {"success": False, "action": "clear_reactions", "details": t("exec.message.missing_multi_param", locale=self._locale, param1="channel_id", param2="message_id")}

        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "clear_reactions", "details": t("not_found.channel", locale=self._locale, id=channel_id)}

        try:
            message = await channel.fetch_message(message_id)
            await message.clear_reactions()
            return {"success": True, "action": "clear_reactions", "details": t("exec.message.reactions_cleared", locale=self._locale, id=message_id)}
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
            return {"success": False, "action": "clear_reactions", "details": str(e)}

    async def _bulk_delete(self, params: dict, guild: discord.Guild) -> dict:
        """メッセージを一括削除する（14日以内）。"""
        channel_id = params.get("channel_id")
        message_ids = params.get("message_ids", [])
        if not channel_id or not message_ids:
            return {"success": False, "action": "bulk_delete", "details": t("exec.message.missing_multi_param", locale=self._locale, param1="channel_id", param2="message_ids")}

        channel = guild.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            return {"success": False, "action": "bulk_delete", "details": t("not_found.text_channel", locale=self._locale, id=channel_id)}

        try:
            deleted = await channel.delete_messages(message_ids)
            return {"success": True, "action": "bulk_delete", "details": t("exec.message.bulk_deleted", locale=self._locale, count=len(message_ids), channel=channel.name)}
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
            return {"success": False, "action": "bulk_delete", "details": str(e)}

    async def _find_message(self, guild: discord.Guild, message_id: int) -> discord.Message | None:
        """サーバー内のチャンネル・スレッドからメッセージを検索する。"""
        for channel in guild.text_channels:
            try:
                message = await channel.fetch_message(message_id)
                return message
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                continue
        for thread in guild.threads:
            try:
                message = await thread.fetch_message(message_id)
                return message
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                continue
        return None
