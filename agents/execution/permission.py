import discord

from agents.base import ExecutionAgent
from graph.state import AgentState


class PermissionExecutionAgent(ExecutionAgent):
    """Handles channel permission overwrites: set, delete, sync."""

    @property
    def name(self) -> str:
        return "permission_execution"

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
            "set_channel_permission": self._set_channel_permission,
            "delete_channel_permission": self._delete_channel_permission,
            "sync_permissions": self._sync_permissions,
        }
        handler = handlers.get(action)
        if not handler:
            return {"success": False, "action": action, "details": f"Unknown action: {action}"}
        return await handler(params, guild)

    def _resolve_target(self, guild: discord.Guild, target_type: str, target_id: int) -> discord.Role | discord.Member | None:
        if target_type == "member":
            return guild.get_member(target_id)
        return guild.get_role(target_id)

    async def _set_channel_permission(self, params: dict, guild: discord.Guild) -> dict:
        channel_id = params.get("channel_id")
        target_type = params.get("target_type", "role")
        target_id = params.get("target_id")
        if not channel_id:
            return {"success": False, "action": "set_channel_permission", "details": "Missing 'channel_id' parameter"}
        if not target_id:
            return {"success": False, "action": "set_channel_permission", "details": "Missing 'target_id' parameter"}

        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "set_channel_permission", "details": f"Channel {channel_id} not found"}

        target = self._resolve_target(guild, target_type, target_id)
        if not target:
            label = "Member" if target_type == "member" else "Role"
            return {"success": False, "action": "set_channel_permission", "details": f"{label} {target_id} not found"}

        allow_perms = params.get("allow_perms", 0)
        deny_perms = params.get("deny_perms", 0)

        overwrite = discord.PermissionOverwrite(
            allow=discord.Permissions(allow_perms),
            deny=discord.Permissions(deny_perms),
        )

        try:
            await channel.set_permissions(target, overwrite=overwrite)
            target_name = target.display_name if hasattr(target, "display_name") else target.name
            return {"success": True, "action": "set_channel_permission", "details": f"Set permissions for {target_name} on #{channel.name}"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "set_channel_permission", "details": str(e)}

    async def _delete_channel_permission(self, params: dict, guild: discord.Guild) -> dict:
        channel_id = params.get("channel_id")
        overwrite_id = params.get("overwrite_id")
        if not channel_id:
            return {"success": False, "action": "delete_channel_permission", "details": "Missing 'channel_id' parameter"}
        if not overwrite_id:
            return {"success": False, "action": "delete_channel_permission", "details": "Missing 'overwrite_id' parameter"}

        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "delete_channel_permission", "details": f"Channel {channel_id} not found"}

        # Resolve the target (role or member) for deletion
        target = guild.get_role(overwrite_id) or guild.get_member(overwrite_id)
        if not target:
            return {"success": False, "action": "delete_channel_permission", "details": f"Target {overwrite_id} not found"}

        try:
            await channel.set_permissions(target, overwrite=None)
            target_name = target.display_name if hasattr(target, "display_name") else target.name
            return {"success": True, "action": "delete_channel_permission", "details": f"Cleared permissions for {target_name} on #{channel.name}"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "delete_channel_permission", "details": str(e)}

    async def _sync_permissions(self, params: dict, guild: discord.Guild) -> dict:
        channel_id = params.get("channel_id")
        category_id = params.get("category_id")
        if not channel_id:
            return {"success": False, "action": "sync_permissions", "details": "Missing 'channel_id' parameter"}

        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "sync_permissions", "details": f"Channel {channel_id} not found"}

        # If category_id is provided, verify it matches or set the category first
        if category_id:
            category = guild.get_channel(category_id)
            if category and isinstance(category, discord.CategoryChannel):
                try:
                    await channel.edit(category=category)
                except (discord.Forbidden, discord.HTTPException):
                    return {"success": False, "action": "sync_permissions", "details": f"Failed to move channel to category {category_id}"}

        # Sync permissions with category
        try:
            await channel.edit(sync_permissions=True)
            return {"success": True, "action": "sync_permissions", "details": f"Synced permissions for #{channel.name} with its category"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "sync_permissions", "details": str(e)}
