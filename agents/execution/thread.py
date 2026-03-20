import discord

from agents.base import ExecutionAgent
from graph.state import AgentState


class ThreadExecutionAgent(ExecutionAgent):
    """Handles thread operations (create, edit, archive, lock, membership)."""

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
            "create": self._create,
            "edit": self._edit,
            "delete": self._delete,
            "add_member": self._add_member,
            "join": self._join,
            "leave": self._leave,
        }
        handler = handlers.get(action)
        if not handler:
            return {"success": False, "action": action, "details": f"Unknown action: {action}"}
        return await handler(params, guild)

    async def _create(self, params: dict, guild: discord.Guild) -> dict:
        channel_id = params.get("channel_id")
        name = params.get("name")
        if not channel_id:
            return {"success": False, "action": "create", "details": "Missing 'channel_id' parameter"}
        if not name:
            return {"success": False, "action": "create", "details": "Missing 'name' parameter"}

        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "create", "details": f"Channel {channel_id} not found"}

        thread_type = discord.ChannelType.public_thread
        type_str = params.get("type", "public").lower()
        if type_str == "private":
            thread_type = discord.ChannelType.private_thread

        kwargs: dict = {"name": name, "type": thread_type}
        if "auto_archive_duration" in params:
            kwargs["auto_archive_duration"] = params["auto_archive_duration"]

        try:
            thread = await channel.create_thread(**kwargs)
            return {"success": True, "action": "create", "details": f"Created thread '{thread.name}' ({thread.id})"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "create", "details": str(e)}

    async def _edit(self, params: dict, guild: discord.Guild) -> dict:
        thread_id = params.get("thread_id")
        if not thread_id:
            return {"success": False, "action": "edit", "details": "Missing 'thread_id' parameter"}

        thread = guild.get_thread(thread_id)
        if not thread:
            # Fallback: fetch from channel threads
            thread = await self._find_thread(guild, thread_id)
        if not thread:
            return {"success": False, "action": "edit", "details": f"Thread {thread_id} not found"}

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
            return {"success": False, "action": "edit", "details": "No editable parameters provided"}

        try:
            await thread.edit(**kwargs)
            return {"success": True, "action": "edit", "details": f"Edited thread '{thread.name}'"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit", "details": str(e)}

    async def _delete(self, params: dict, guild: discord.Guild) -> dict:
        thread_id = params.get("thread_id")
        if not thread_id:
            return {"success": False, "action": "delete", "details": "Missing 'thread_id' parameter"}

        thread = guild.get_thread(thread_id)
        if not thread:
            thread = await self._find_thread(guild, thread_id)
        if not thread:
            return {"success": False, "action": "delete", "details": f"Thread {thread_id} not found"}

        thread_name = thread.name
        try:
            await thread.delete()
            return {"success": True, "action": "delete", "details": f"Deleted thread '{thread_name}'"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "delete", "details": str(e)}

    async def _add_member(self, params: dict, guild: discord.Guild) -> dict:
        thread_id = params.get("thread_id")
        member_id = params.get("member_id")
        if not thread_id:
            return {"success": False, "action": "add_member", "details": "Missing 'thread_id' parameter"}
        if not member_id:
            return {"success": False, "action": "add_member", "details": "Missing 'member_id' parameter"}

        thread = guild.get_thread(thread_id)
        if not thread:
            thread = await self._find_thread(guild, thread_id)
        if not thread:
            return {"success": False, "action": "add_member", "details": f"Thread {thread_id} not found"}

        member = guild.get_member(member_id)
        if not member:
            return {"success": False, "action": "add_member", "details": f"Member {member_id} not found"}

        try:
            await thread.add_member(member)
            return {"success": True, "action": "add_member", "details": f"Added {member.display_name} to thread '{thread.name}'"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "add_member", "details": str(e)}

    async def _join(self, params: dict, guild: discord.Guild) -> dict:
        thread_id = params.get("thread_id")
        if not thread_id:
            return {"success": False, "action": "join", "details": "Missing 'thread_id' parameter"}

        thread = guild.get_thread(thread_id)
        if not thread:
            thread = await self._find_thread(guild, thread_id)
        if not thread:
            return {"success": False, "action": "join", "details": f"Thread {thread_id} not found"}

        try:
            await thread.join()
            return {"success": True, "action": "join", "details": f"Joined thread '{thread.name}'"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "join", "details": str(e)}

    async def _leave(self, params: dict, guild: discord.Guild) -> dict:
        thread_id = params.get("thread_id")
        if not thread_id:
            return {"success": False, "action": "leave", "details": "Missing 'thread_id' parameter"}

        thread = guild.get_thread(thread_id)
        if not thread:
            thread = await self._find_thread(guild, thread_id)
        if not thread:
            return {"success": False, "action": "leave", "details": f"Thread {thread_id} not found"}

        try:
            await thread.leave()
            return {"success": True, "action": "leave", "details": f"Left thread '{thread.name}'"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "leave", "details": str(e)}

    async def _find_thread(self, guild: discord.Guild, thread_id: int) -> discord.Thread | None:
        """Search active threads in the guild for a thread by ID."""
        for channel in guild.text_channels:
            for thread in channel.threads:
                if thread.id == thread_id:
                    return thread
        return None
