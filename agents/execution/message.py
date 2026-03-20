import discord

from agents.base import ExecutionAgent
from graph.state import AgentState


class MessageExecutionAgent(ExecutionAgent):
    """Handles message send, edit, delete, pin, and reaction operations."""

    @property
    def name(self) -> str:
        return "message_execution"

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
            return {"success": False, "action": action, "details": f"Unknown action: {action}"}
        return await handler(params, guild)

    async def _send(self, params: dict, guild: discord.Guild) -> dict:
        channel_id = params.get("channel_id")
        content = params.get("content", "")
        if not channel_id:
            return {"success": False, "action": "send", "details": "Missing 'channel_id' parameter"}

        channel = guild.get_channel(channel_id)
        if not channel or not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
            return {"success": False, "action": "send", "details": f"Sendable channel {channel_id} not found"}

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
            return {"success": True, "action": "send", "details": f"Sent message in #{channel.name} ({message.id})"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "send", "details": str(e)}

    async def _edit(self, params: dict, guild: discord.Guild) -> dict:
        message_id = params.get("message_id")
        content = params.get("content")
        if not message_id:
            return {"success": False, "action": "edit", "details": "Missing 'message_id' parameter"}
        if not content:
            return {"success": False, "action": "edit", "details": "Missing 'content' parameter"}

        try:
            message = await self._find_message(guild, message_id)
            if not message:
                return {"success": False, "action": "edit", "details": f"Message {message_id} not found"}
            await message.edit(content=content)
            return {"success": True, "action": "edit", "details": f"Edited message {message_id}"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit", "details": str(e)}

    async def _delete(self, params: dict, guild: discord.Guild) -> dict:
        message_id = params.get("message_id")
        if not message_id:
            return {"success": False, "action": "delete", "details": "Missing 'message_id' parameter"}

        try:
            message = await self._find_message(guild, message_id)
            if not message:
                return {"success": False, "action": "delete", "details": f"Message {message_id} not found"}
            await message.delete()
            return {"success": True, "action": "delete", "details": f"Deleted message {message_id}"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "delete", "details": str(e)}

    async def _pin(self, params: dict, guild: discord.Guild) -> dict:
        channel_id = params.get("channel_id")
        message_id = params.get("message_id")
        if not channel_id or not message_id:
            return {"success": False, "action": "pin", "details": "Missing 'channel_id' or 'message_id' parameter"}

        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "pin", "details": f"Channel {channel_id} not found"}

        try:
            message = await channel.fetch_message(message_id)
            await message.pin()
            return {"success": True, "action": "pin", "details": f"Pinned message {message_id} in #{channel.name}"}
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
            return {"success": False, "action": "pin", "details": str(e)}

    async def _unpin(self, params: dict, guild: discord.Guild) -> dict:
        channel_id = params.get("channel_id")
        message_id = params.get("message_id")
        if not channel_id or not message_id:
            return {"success": False, "action": "unpin", "details": "Missing 'channel_id' or 'message_id' parameter"}

        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "unpin", "details": f"Channel {channel_id} not found"}

        try:
            message = await channel.fetch_message(message_id)
            await message.unpin()
            return {"success": True, "action": "unpin", "details": f"Unpinned message {message_id} in #{channel.name}"}
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
            return {"success": False, "action": "unpin", "details": str(e)}

    async def _add_reaction(self, params: dict, guild: discord.Guild) -> dict:
        channel_id = params.get("channel_id")
        message_id = params.get("message_id")
        emoji = params.get("emoji")
        if not channel_id or not message_id or not emoji:
            return {"success": False, "action": "add_reaction", "details": "Missing required parameters (channel_id, message_id, emoji)"}

        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "add_reaction", "details": f"Channel {channel_id} not found"}

        try:
            message = await channel.fetch_message(message_id)
            await message.add_reaction(emoji)
            return {"success": True, "action": "add_reaction", "details": f"Added reaction {emoji} to message {message_id}"}
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
            return {"success": False, "action": "add_reaction", "details": str(e)}

    async def _remove_reaction(self, params: dict, guild: discord.Guild) -> dict:
        channel_id = params.get("channel_id")
        message_id = params.get("message_id")
        emoji = params.get("emoji")
        member_id = params.get("member_id")
        if not channel_id or not message_id or not emoji:
            return {"success": False, "action": "remove_reaction", "details": "Missing required parameters (channel_id, message_id, emoji)"}

        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "remove_reaction", "details": f"Channel {channel_id} not found"}

        try:
            message = await channel.fetch_message(message_id)
            if member_id:
                member = guild.get_member(member_id)
                if member:
                    await message.remove_reaction(emoji, member)
                else:
                    return {"success": False, "action": "remove_reaction", "details": f"Member {member_id} not found"}
            else:
                # Remove bot's own reaction
                await message.remove_reaction(emoji, guild.me)
            return {"success": True, "action": "remove_reaction", "details": f"Removed reaction {emoji} from message {message_id}"}
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
            return {"success": False, "action": "remove_reaction", "details": str(e)}

    async def _clear_reactions(self, params: dict, guild: discord.Guild) -> dict:
        channel_id = params.get("channel_id")
        message_id = params.get("message_id")
        if not channel_id or not message_id:
            return {"success": False, "action": "clear_reactions", "details": "Missing 'channel_id' or 'message_id' parameter"}

        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "clear_reactions", "details": f"Channel {channel_id} not found"}

        try:
            message = await channel.fetch_message(message_id)
            await message.clear_reactions()
            return {"success": True, "action": "clear_reactions", "details": f"Cleared all reactions from message {message_id}"}
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
            return {"success": False, "action": "clear_reactions", "details": str(e)}

    async def _bulk_delete(self, params: dict, guild: discord.Guild) -> dict:
        channel_id = params.get("channel_id")
        message_ids = params.get("message_ids", [])
        if not channel_id or not message_ids:
            return {"success": False, "action": "bulk_delete", "details": "Missing 'channel_id' or 'message_ids' parameter"}

        channel = guild.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            return {"success": False, "action": "bulk_delete", "details": f"Text channel {channel_id} not found"}

        try:
            # Discord bulk_delete requires message objects or snowflakes (within 14 days)
            deleted = await channel.delete_messages(message_ids)
            return {"success": True, "action": "bulk_delete", "details": f"Bulk deleted {len(message_ids)} message(s) in #{channel.name}"}
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
            return {"success": False, "action": "bulk_delete", "details": str(e)}

    async def _find_message(self, guild: discord.Guild, message_id: int) -> discord.Message | None:
        """Search through guild channels for a message by ID."""
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
