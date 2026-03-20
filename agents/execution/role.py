import discord

from agents.base import ExecutionAgent
from graph.state import AgentState


class RoleExecutionAgent(ExecutionAgent):
    """Handles role create, edit, delete, reorder, assign, and revoke operations."""

    @property
    def name(self) -> str:
        return "role_execution"

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
            "assign": self._assign,
            "revoke": self._revoke,
        }
        handler = handlers.get(action)
        if not handler:
            return {"success": False, "action": action, "details": f"Unknown action: {action}"}
        return await handler(params, guild)

    async def _create(self, params: dict, guild: discord.Guild) -> dict:
        name = params.get("name")
        if not name:
            return {"success": False, "action": "create", "details": "Missing 'name' parameter"}

        kwargs: dict = {"name": name}

        if "color" in params:
            kwargs["colour"] = params["color"]
        if "permissions" in params:
            kwargs["permissions"] = discord.Permissions(params["permissions"])
        if "hoist" in params:
            kwargs["hoist"] = params["hoist"]
        if "mentionable" in params:
            kwargs["mentionable"] = params["mentionable"]

        try:
            role = await guild.create_role(**kwargs)
            return {"success": True, "action": "create", "details": f"Created role '{role.name}' ({role.id})"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "create", "details": str(e)}

    async def _edit(self, params: dict, guild: discord.Guild) -> dict:
        role_id = params.get("role_id")
        if not role_id:
            return {"success": False, "action": "edit", "details": "Missing 'role_id' parameter"}

        role = guild.get_role(role_id)
        if not role:
            return {"success": False, "action": "edit", "details": f"Role {role_id} not found"}

        kwargs: dict = {}
        if "name" in params:
            kwargs["name"] = params["name"]
        if "color" in params:
            kwargs["colour"] = params["color"]
        if "permissions" in params:
            kwargs["permissions"] = discord.Permissions(params["permissions"])
        if "hoist" in params:
            kwargs["hoist"] = params["hoist"]
        if "mentionable" in params:
            kwargs["mentionable"] = params["mentionable"]

        if not kwargs:
            return {"success": False, "action": "edit", "details": "No editable parameters provided"}

        try:
            await role.edit(**kwargs)
            return {"success": True, "action": "edit", "details": f"Edited role '{role.name}'"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit", "details": str(e)}

    async def _delete(self, params: dict, guild: discord.Guild) -> dict:
        role_id = params.get("role_id")
        if not role_id:
            return {"success": False, "action": "delete", "details": "Missing 'role_id' parameter"}

        role = guild.get_role(role_id)
        if not role:
            return {"success": False, "action": "delete", "details": f"Role {role_id} not found"}

        role_name = role.name
        try:
            await role.delete()
            return {"success": True, "action": "delete", "details": f"Deleted role '{role_name}'"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "delete", "details": str(e)}

    async def _reorder(self, params: dict, guild: discord.Guild) -> dict:
        roles = params.get("roles", [])
        if not roles:
            return {"success": False, "action": "reorder", "details": "Missing 'roles' parameter"}

        # Discord expects list of Role objects or dicts with id and position
        try:
            await guild.edit_role_positions(roles)
            return {"success": True, "action": "reorder", "details": f"Reordered {len(roles)} role(s)"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "reorder", "details": str(e)}

    async def _assign(self, params: dict, guild: discord.Guild) -> dict:
        member_id = params.get("member_id")
        role_id = params.get("role_id")
        if not member_id:
            return {"success": False, "action": "assign", "details": "Missing 'member_id' parameter"}
        if not role_id:
            return {"success": False, "action": "assign", "details": "Missing 'role_id' parameter"}

        member = guild.get_member(member_id)
        if not member:
            return {"success": False, "action": "assign", "details": f"Member {member_id} not found"}

        role = guild.get_role(role_id)
        if not role:
            return {"success": False, "action": "assign", "details": f"Role {role_id} not found"}

        try:
            await member.add_roles(role)
            return {"success": True, "action": "assign", "details": f"Assigned '{role.name}' to {member.display_name}"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "assign", "details": str(e)}

    async def _revoke(self, params: dict, guild: discord.Guild) -> dict:
        member_id = params.get("member_id")
        role_id = params.get("role_id")
        if not member_id:
            return {"success": False, "action": "revoke", "details": "Missing 'member_id' parameter"}
        if not role_id:
            return {"success": False, "action": "revoke", "details": "Missing 'role_id' parameter"}

        member = guild.get_member(member_id)
        if not member:
            return {"success": False, "action": "revoke", "details": f"Member {member_id} not found"}

        role = guild.get_role(role_id)
        if not role:
            return {"success": False, "action": "revoke", "details": f"Role {role_id} not found"}

        try:
            await member.remove_roles(role)
            return {"success": True, "action": "revoke", "details": f"Revoked '{role.name}' from {member.display_name}"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "revoke", "details": str(e)}
