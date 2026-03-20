import discord

from agents.base import MultiActionExecutionAgent
from graph.state import AgentState


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
            return {"success": False, "action": action, "details": f"Unknown action: {action}"}
        return await handler(params, guild)

    async def _create(self, params: dict, guild: discord.Guild) -> dict:
        """チャンネルを作成する。"""
        name = params.get("name")
        if not name:
            return {"success": False, "action": "create", "details": "Missing 'name' parameter"}

        channel_type = discord.ChannelType.text
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
            channel = await guild.create_text_channel(
                name=name,
                category=category,
                topic=params.get("topic"),
                nsfw=params.get("nsfw", False),
            ) if channel_type in (discord.ChannelType.text, discord.ChannelType.news) else await guild.create_voice_channel(
                name=name,
                category=category,
            )
            return {"success": True, "action": "create", "details": f"Created #{channel.name} ({channel.id})"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "create", "details": str(e)}

    async def _edit(self, params: dict, guild: discord.Guild) -> dict:
        """チャンネルを編集する。"""
        channel_id = params.get("channel_id")
        if not channel_id:
            return {"success": False, "action": "edit", "details": "Missing 'channel_id' parameter"}
        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "edit", "details": f"Channel {channel_id} not found"}

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
            return {"success": False, "action": "edit", "details": "No editable parameters provided"}

        try:
            await channel.edit(**kwargs)
            return {"success": True, "action": "edit", "details": f"Edited #{channel.name}"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit", "details": str(e)}

    async def _delete(self, params: dict, guild: discord.Guild) -> dict:
        """チャンネルを削除する。"""
        channel_id = params.get("channel_id")
        if not channel_id:
            return {"success": False, "action": "delete", "details": "Missing 'channel_id' parameter"}
        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "delete", "details": f"Channel {channel_id} not found"}
        channel_name = channel.name
        try:
            await channel.delete()
            return {"success": True, "action": "delete", "details": f"Deleted #{channel_name}"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "delete", "details": str(e)}

    async def _reorder(self, params: dict, guild: discord.Guild) -> dict:
        """チャンネルの並び順を変更する。"""
        positions = params.get("channel_positions", [])
        if not positions:
            return {"success": False, "action": "reorder", "details": "Missing 'channel_positions' parameter"}
        try:
            await guild.edit_channel_positions(positions)
            return {"success": True, "action": "reorder", "details": f"Reordered {len(positions)} channel(s)"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "reorder", "details": str(e)}
