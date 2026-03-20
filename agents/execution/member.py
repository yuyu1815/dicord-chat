import discord

from agents.base import ExecutionAgent
from graph.state import AgentState


class MemberExecutionAgent(ExecutionAgent):
    """Handles member moderation: nickname, roles, timeout, kick, ban, unban."""

    @property
    def name(self) -> str:
        return "member_execution"

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
            "edit_nickname": self._edit_nickname,
            "edit_roles": self._edit_roles,
            "timeout": self._timeout,
            "kick": self._kick,
            "ban": self._ban,
            "unban": self._unban,
        }
        handler = handlers.get(action)
        if not handler:
            return {"success": False, "action": action, "details": f"Unknown action: {action}"}
        return await handler(params, guild)

    async def _edit_nickname(self, params: dict, guild: discord.Guild) -> dict:
        member_id = params.get("member_id")
        nickname = params.get("nickname")
        if not member_id:
            return {"success": False, "action": "edit_nickname", "details": "Missing 'member_id' parameter"}

        member = guild.get_member(member_id)
        if not member:
            return {"success": False, "action": "edit_nickname", "details": f"Member {member_id} not found"}

        try:
            await member.edit(nick=nickname)
            if nickname:
                return {"success": True, "action": "edit_nickname", "details": f"Set nickname of {member.display_name} to '{nickname}'"}
            return {"success": True, "action": "edit_nickname", "details": f"Reset nickname of {member.display_name}"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit_nickname", "details": str(e)}

    async def _edit_roles(self, params: dict, guild: discord.Guild) -> dict:
        member_id = params.get("member_id")
        if not member_id:
            return {"success": False, "action": "edit_roles", "details": "Missing 'member_id' parameter"}

        member = guild.get_member(member_id)
        if not member:
            return {"success": False, "action": "edit_roles", "details": f"Member {member_id} not found"}

        add_role_ids = params.get("add_roles", [])
        remove_role_ids = params.get("remove_roles", [])

        add_roles = []
        for rid in add_role_ids:
            role = guild.get_role(rid)
            if role:
                add_roles.append(role)

        remove_roles = []
        for rid in remove_role_ids:
            role = guild.get_role(rid)
            if role:
                remove_roles.append(role)

        if not add_roles and not remove_roles:
            return {"success": False, "action": "edit_roles", "details": "No roles specified to add or remove"}

        try:
            await member.edit(roles=[r for r in member.roles if r not in remove_roles] + add_roles)
            parts = []
            if add_roles:
                parts.append(f"added {len(add_roles)} role(s)")
            if remove_roles:
                parts.append(f"removed {len(remove_roles)} role(s)")
            return {"success": True, "action": "edit_roles", "details": f"Edited roles for {member.display_name}: {', '.join(parts)}"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit_roles", "details": str(e)}

    async def _timeout(self, params: dict, guild: discord.Guild) -> dict:
        member_id = params.get("member_id")
        duration_minutes = params.get("duration_minutes")
        reason = params.get("reason")
        if not member_id:
            return {"success": False, "action": "timeout", "details": "Missing 'member_id' parameter"}
        if duration_minutes is None:
            return {"success": False, "action": "timeout", "details": "Missing 'duration_minutes' parameter"}

        member = guild.get_member(member_id)
        if not member:
            return {"success": False, "action": "timeout", "details": f"Member {member_id} not found"}

        from datetime import datetime, timedelta, timezone
        until = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)

        try:
            await member.edit(timed_out_until=until, reason=reason)
            return {"success": True, "action": "timeout", "details": f"Timed out {member.display_name} for {duration_minutes} minute(s)"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "timeout", "details": str(e)}

    async def _kick(self, params: dict, guild: discord.Guild) -> dict:
        member_id = params.get("member_id")
        reason = params.get("reason")
        if not member_id:
            return {"success": False, "action": "kick", "details": "Missing 'member_id' parameter"}

        member = guild.get_member(member_id)
        if not member:
            return {"success": False, "action": "kick", "details": f"Member {member_id} not found"}

        try:
            await member.kick(reason=reason)
            return {"success": True, "action": "kick", "details": f"Kicked {member.display_name}"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "kick", "details": str(e)}

    async def _ban(self, params: dict, guild: discord.Guild) -> dict:
        member_id = params.get("member_id")
        reason = params.get("reason")
        delete_message_days = params.get("delete_message_days", 0)
        if not member_id:
            return {"success": False, "action": "ban", "details": "Missing 'member_id' parameter"}

        member = guild.get_member(member_id)
        if not member:
            return {"success": False, "action": "ban", "details": f"Member {member_id} not found"}

        try:
            await member.ban(reason=reason, delete_message_days=delete_message_days)
            return {"success": True, "action": "ban", "details": f"Banned {member.display_name}"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "ban", "details": str(e)}

    async def _unban(self, params: dict, guild: discord.Guild) -> dict:
        user_id = params.get("user_id")
        reason = params.get("reason")
        if not user_id:
            return {"success": False, "action": "unban", "details": "Missing 'user_id' parameter"}

        # Create a partial user object for the ban lookup
        user = discord.Object(id=user_id)
        try:
            await guild.unban(user, reason=reason)
            return {"success": True, "action": "unban", "details": f"Unbanned user {user_id}"}
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
            return {"success": False, "action": "unban", "details": str(e)}
