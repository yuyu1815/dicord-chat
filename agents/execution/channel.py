import discord

from agents.base import MultiActionExecutionAgent
from i18n import t


class ChannelExecutionAgent(MultiActionExecutionAgent):
    """テキスト・ボイスチャンネルの操作を行うエージェント。"""

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "create": ["manage_channels"],
        "edit": ["manage_channels"],
        "delete": ["manage_channels"],
        "reorder": ["manage_channels"],
    }

    @property
    def name(self) -> str:
        return "channel_execution"

    async def _dispatch(self, action: str, params: dict, guild: discord.Guild) -> dict:
        handlers = {
            "create": self._create,
            "edit": self._edit,
            "delete": self._delete,
            "reorder": self._reorder,
        }
        handler = handlers.get(action)
        if not handler:
            return {"success": False, "action": action, "details": t("err.unknown_action", locale=self._locale, action=action)}
        return await handler(params, guild)

    async def _create(self, params: dict, guild: discord.Guild) -> dict:
        """チャンネルを作成する。"""
        name = params.get("name")
        if not name:
            return {"success": False, "action": "create", "details": t("exec.missing_param", locale=self._locale, param="name")}

        type_str = params.get("type", "text").lower()
        type_map = {
            "text": discord.ChannelType.text,
            "voice": discord.ChannelType.voice,
            "announcement": discord.ChannelType.news,
            "stage": discord.ChannelType.stage_voice,
        }
        channel_type = type_map.get(type_str, discord.ChannelType.text)

        category_id = params.get("category_id")
        category = guild.get_channel(category_id) if category_id else None

        try:
            if channel_type == discord.ChannelType.stage_voice:
                channel = await guild.create_stage_channel(
                    name=name,
                    category=category,
                )
            elif channel_type == discord.ChannelType.news:
                channel = await guild.create_text_channel(
                    name=name,
                    category=category,
                    topic=params.get("topic"),
                    nsfw=params.get("nsfw", False),
                    type=discord.ChannelType.news,
                )
            elif channel_type == discord.ChannelType.voice:
                channel = await guild.create_voice_channel(
                    name=name,
                    category=category,
                )
            else:
                channel = await guild.create_text_channel(
                    name=name,
                    category=category,
                    topic=params.get("topic"),
                    nsfw=params.get("nsfw", False),
                )
            return {"success": True, "action": "create", "details": t("exec.channel.created", locale=self._locale, name=channel.name, id=channel.id)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "create", "details": str(e)}

    async def _edit(self, params: dict, guild: discord.Guild) -> dict:
        """チャンネルを編集する。"""
        channel_id = params.get("channel_id")
        if not channel_id:
            return {"success": False, "action": "edit", "details": t("exec.missing_param", locale=self._locale, param="channel_id")}
        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "edit", "details": t("not_found.channel", locale=self._locale, id=channel_id)}

        kwargs = {}
        if "name" in params:
            kwargs["name"] = params["name"]
        if "topic" in params:
            kwargs["topic"] = params["topic"]
        if "nsfw" in params:
            kwargs["nsfw"] = params["nsfw"]
        if "slowmode" in params:
            kwargs["slowmode_delay"] = params["slowmode"]

        if not kwargs:
            return {"success": False, "action": "edit", "details": t("exec.no_editable_params", locale=self._locale)}

        try:
            await channel.edit(**kwargs)
            return {"success": True, "action": "edit", "details": t("exec.channel.edited", locale=self._locale, name=channel.name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit", "details": str(e)}

    async def _delete(self, params: dict, guild: discord.Guild) -> dict:
        """チャンネルを削除する。"""
        channel_id = params.get("channel_id")
        if not channel_id:
            return {"success": False, "action": "delete", "details": t("exec.missing_param", locale=self._locale, param="channel_id")}
        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "delete", "details": t("not_found.channel", locale=self._locale, id=channel_id)}
        channel_name = channel.name
        try:
            await channel.delete()
            return {"success": True, "action": "delete", "details": t("exec.channel.deleted", locale=self._locale, name=channel_name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "delete", "details": str(e)}

    async def _reorder(self, params: dict, guild: discord.Guild) -> dict:
        """チャンネルの並び順を変更する。"""
        positions = params.get("channel_positions", [])
        if not positions:
            return {"success": False, "action": "reorder", "details": t("exec.channel.missing_positions", locale=self._locale)}
        try:
            await guild.edit_channel_positions(positions)
            return {"success": True, "action": "reorder", "details": t("exec.channel.reordered", locale=self._locale, count=len(positions))}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "reorder", "details": str(e)}
