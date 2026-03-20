import discord

from agents.base import ExecutionAgent
from graph.state import AgentState


class CategoryExecutionAgent(ExecutionAgent):
    """Handles category (channel group) operations."""

    @property
    def name(self) -> str:
        return "category_execution"

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
        }
        handler = handlers.get(action)
        if not handler:
            return {"success": False, "action": action, "details": f"Unknown action: {action}"}
        return await handler(params, guild)

    async def _create(self, params: dict, guild: discord.Guild) -> dict:
        name = params.get("name")
        if not name:
            return {"success": False, "action": "create", "details": "Missing 'name' parameter"}

        overwrites = []
        raw_overwrites = params.get("overwrites", [])
        for ow in raw_overwrites:
            target_id = ow.get("target_id")
            target_type = ow.get("target_type", "role")
            allow = ow.get("allow", 0)
            deny = ow.get("deny", 0)
            if target_type == "member":
                target = guild.get_member(target_id)
            else:
                target = guild.get_role(target_id)
            if not target:
                continue
            overwrites.append(
                discord.PermissionOverwrite(
                    target=target,
                    allow=discord.Permissions(allow),
                    deny=discord.Permissions(deny),
                )
            )

        kwargs = {"name": name}
        if params.get("position") is not None:
            kwargs["position"] = params["position"]
        if overwrites:
            kwargs["overwrites"] = overwrites

        try:
            category = await guild.create_category_channel(**kwargs)
            return {"success": True, "action": "create", "details": f"Created category '{category.name}' ({category.id})"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "create", "details": str(e)}

    async def _edit(self, params: dict, guild: discord.Guild) -> dict:
        category_id = params.get("category_id")
        if not category_id:
            return {"success": False, "action": "edit", "details": "Missing 'category_id' parameter"}
        category = guild.get_channel(category_id)
        if not category or not isinstance(category, discord.CategoryChannel):
            return {"success": False, "action": "edit", "details": f"Category {category_id} not found"}

        kwargs = {}
        if "name" in params:
            kwargs["name"] = params["name"]
        if "position" in params:
            kwargs["position"] = params["position"]

        if not kwargs:
            return {"success": False, "action": "edit", "details": "No editable parameters provided"}

        try:
            await category.edit(**kwargs)
            return {"success": True, "action": "edit", "details": f"Edited category '{category.name}'"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit", "details": str(e)}

    async def _delete(self, params: dict, guild: discord.Guild) -> dict:
        category_id = params.get("category_id")
        if not category_id:
            return {"success": False, "action": "delete", "details": "Missing 'category_id' parameter"}
        category = guild.get_channel(category_id)
        if not category or not isinstance(category, discord.CategoryChannel):
            return {"success": False, "action": "delete", "details": f"Category {category_id} not found"}
        category_name = category.name
        try:
            await category.delete()
            return {"success": True, "action": "delete", "details": f"Deleted category '{category_name}'"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "delete", "details": str(e)}
