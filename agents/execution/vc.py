import discord

from agents.base import ExecutionAgent
from graph.state import AgentState


class VoiceChannelExecutionAgent(ExecutionAgent):
    """Handles voice channel operations: move, mute, deafen, disconnect, edit."""

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "move_user": ["move_members"],
        "mute": ["mute_members"],
        "unmute": ["mute_members"],
        "deafen": ["deafen_members"],
        "undeafen": ["deafen_members"],
        "disconnect": ["move_members"],
        "edit_channel": ["manage_channels"],
    }

    @property
    def name(self) -> str:
        return "vc_execution"

    async def execute(self, state: AgentState, guild: discord.Guild) -> dict:
        todos = state.get("todos", [])
        my_todos = [t for t in todos if t.get("agent") == self.name and not t.get("_blocked")]
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
            "move_user": self._move_user,
            "mute": self._mute,
            "unmute": self._unmute,
            "deafen": self._deafen,
            "undeafen": self._undeafen,
            "disconnect": self._disconnect,
            "edit_channel": self._edit_channel,
        }
        handler = handlers.get(action)
        if not handler:
            return {"success": False, "action": action, "details": f"Unknown action: {action}"}
        return await handler(params, guild)

    async def _move_user(self, params: dict, guild: discord.Guild) -> dict:
        user_id = params.get("user_id")
        channel_id = params.get("channel_id")
        if not user_id:
            return {"success": False, "action": "move_user", "details": "Missing 'user_id' parameter"}
        if not channel_id:
            return {"success": False, "action": "move_user", "details": "Missing 'channel_id' parameter"}

        member = guild.get_member(user_id)
        if not member:
            return {"success": False, "action": "move_user", "details": f"Member {user_id} not found"}

        channel = guild.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            return {"success": False, "action": "move_user", "details": f"Voice channel {channel_id} not found"}

        try:
            await member.move_to(channel)
            return {"success": True, "action": "move_user", "details": f"Moved {member.display_name} to {channel.name}"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "move_user", "details": str(e)}

    async def _mute(self, params: dict, guild: discord.Guild) -> dict:
        user_id = params.get("user_id")
        if not user_id:
            return {"success": False, "action": "mute", "details": "Missing 'user_id' parameter"}

        member = guild.get_member(user_id)
        if not member:
            return {"success": False, "action": "mute", "details": f"Member {user_id} not found"}

        try:
            await member.edit(mute=True)
            return {"success": True, "action": "mute", "details": f"Server-muted {member.display_name}"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "mute", "details": str(e)}

    async def _unmute(self, params: dict, guild: discord.Guild) -> dict:
        user_id = params.get("user_id")
        if not user_id:
            return {"success": False, "action": "unmute", "details": "Missing 'user_id' parameter"}

        member = guild.get_member(user_id)
        if not member:
            return {"success": False, "action": "unmute", "details": f"Member {user_id} not found"}

        try:
            await member.edit(mute=False)
            return {"success": True, "action": "unmute", "details": f"Server-unmuted {member.display_name}"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "unmute", "details": str(e)}

    async def _deafen(self, params: dict, guild: discord.Guild) -> dict:
        user_id = params.get("user_id")
        if not user_id:
            return {"success": False, "action": "deafen", "details": "Missing 'user_id' parameter"}

        member = guild.get_member(user_id)
        if not member:
            return {"success": False, "action": "deafen", "details": f"Member {user_id} not found"}

        try:
            await member.edit(deafen=True)
            return {"success": True, "action": "deafen", "details": f"Server-deafened {member.display_name}"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "deafen", "details": str(e)}

    async def _undeafen(self, params: dict, guild: discord.Guild) -> dict:
        user_id = params.get("user_id")
        if not user_id:
            return {"success": False, "action": "undeafen", "details": "Missing 'user_id' parameter"}

        member = guild.get_member(user_id)
        if not member:
            return {"success": False, "action": "undeafen", "details": f"Member {user_id} not found"}

        try:
            await member.edit(deafen=False)
            return {"success": True, "action": "undeafen", "details": f"Server-undeafened {member.display_name}"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "undeafen", "details": str(e)}

    async def _disconnect(self, params: dict, guild: discord.Guild) -> dict:
        user_id = params.get("user_id")
        if not user_id:
            return {"success": False, "action": "disconnect", "details": "Missing 'user_id' parameter"}

        member = guild.get_member(user_id)
        if not member:
            return {"success": False, "action": "disconnect", "details": f"Member {user_id} not found"}

        try:
            await member.move_to(None)
            return {"success": True, "action": "disconnect", "details": f"Disconnected {member.display_name} from voice"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "disconnect", "details": str(e)}

    async def _edit_channel(self, params: dict, guild: discord.Guild) -> dict:
        channel_id = params.get("channel_id")
        if not channel_id:
            return {"success": False, "action": "edit_channel", "details": "Missing 'channel_id' parameter"}

        channel = guild.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            return {"success": False, "action": "edit_channel", "details": f"Voice channel {channel_id} not found"}

        kwargs: dict = {}
        if "name" in params:
            kwargs["name"] = params["name"]
        if "bitrate" in params:
            kwargs["bitrate"] = params["bitrate"]
        if "user_limit" in params:
            kwargs["user_limit"] = params["user_limit"]

        if not kwargs:
            return {"success": False, "action": "edit_channel", "details": "No editable parameters provided"}

        try:
            await channel.edit(**kwargs)
            return {"success": True, "action": "edit_channel", "details": f"Edited voice channel '{channel.name}'"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit_channel", "details": str(e)}
