import discord

from agents.base import ExecutionAgent
from graph.state import AgentState


class ChannelExecutionAgent(ExecutionAgent):
    """Handles text and voice channel operations."""

    @property
    def name(self) -> str:
        return "channel_execution"

    async def execute(self, state: AgentState, guild: discord.Guild) -> dict:
        todos = state.get("todos", [])
        my_todos = [t for t in todos if t.get("agent") == self.name]
        if not my_todos:
            return {"success": False, "action": "none", "details": "No matching action found"}

        results = []
        for todo in my_todos:
            action = todo.get("action", "")
            params = todo.get("params", {})
            result = await self._dispatch(action, params, guild)
            results.append(result)

        details = "; ".join(r["details"] for r in results)
        all_ok = all(r["success"] for r in results)
        return {"success": all_ok, "action": ", ".join(r["action"] for r in results), "details": details}

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
        positions = params.get("channel_positions", [])
        if not positions:
            return {"success": False, "action": "reorder", "details": "Missing 'channel_positions' parameter"}
        try:
            await guild.edit_channel_positions(positions)
            return {"success": True, "action": "reorder", "details": f"Reordered {len(positions)} channel(s)"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "reorder", "details": str(e)}
