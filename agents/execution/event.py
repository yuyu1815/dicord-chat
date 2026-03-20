import datetime

import discord
from discord import HTTPException

from agents.base import ExecutionAgent
from graph.state import AgentState

NAME = "event_execution"

ACTION_HANDLERS: dict[str, str] = {
    "create": "Create scheduled event",
    "edit": "Edit scheduled event",
    "delete": "Delete scheduled event",
}


class EventExecutionAgent(ExecutionAgent):
    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "create": ["manage_events"],
        "edit": ["manage_events"],
        "delete": ["manage_events"],
    }

    @property
    def name(self) -> str:
        return NAME

    async def execute(self, state: AgentState, guild: discord.Guild) -> dict:
        action_name = self._find_action(state)
        if not action_name:
            return {"success": False, "action": "none", "details": "No matching todo found."}

        handler = ACTION_HANDLERS.get(action_name)
        if not handler:
            return {"success": False, "action": action_name, "details": f"Unknown action: {action_name}"}

        params = next(
            (t["params"] for t in state["todos"] if t.get("agent") == NAME and t.get("action") == action_name),
            {},
        )

        try:
            return await getattr(self, f"_do_{action_name}")(guild, params)
        except discord.Forbidden:
            return {"success": False, "action": action_name, "details": "Missing permissions."}
        except discord.NotFound:
            return {"success": False, "action": action_name, "details": "Event not found."}
        except HTTPException as exc:
            return {"success": False, "action": action_name, "details": f"API error: {exc.text}"}

    def _find_action(self, state: AgentState) -> str | None:
        for todo in state.get("todos", []):
            if todo.get("agent") == NAME and not todo.get("_blocked"):
                return todo.get("action")
        return None

    def _parse_event_type(self, raw: str | None) -> discord.EntityType:
        type_map = {
            "stage_instance": discord.EntityType.stage_instance,
            "voice": discord.EntityType.voice,
            "external": discord.EntityType.external,
        }
        value = raw or "external"
        return type_map.get(value, discord.EntityType.external)

    async def _do_create(self, guild: discord.Guild, params: dict) -> dict:
        entity_type = self._parse_event_type(params.get("entity_type"))
        kwargs: dict = {
            "name": params["name"],
            "start_time": datetime.datetime.fromisoformat(params["start_time"]),
            "entity_type": entity_type,
        }
        if "description" in params:
            kwargs["description"] = params["description"]
        if "end_time" in params:
            kwargs["end_time"] = datetime.datetime.fromisoformat(params["end_time"])
        if "channel_id" in params and entity_type != discord.EntityType.external:
            kwargs["channel"] = guild.get_channel(params["channel_id"])
        if entity_type == discord.EntityType.external and "location" in params:
            kwargs["location"] = params["location"]

        event = await guild.create_scheduled_event(**kwargs)
        return {"success": True, "action": "create", "details": f"Created event '{event.name}'."}

    async def _do_edit(self, guild: discord.Guild, params: dict) -> dict:
        event = guild.get_scheduled_event(params["event_id"])
        if not event:
            return {"success": False, "action": "edit", "details": "Event not found."}

        kwargs: dict = {}
        for key in ("name", "description", "status"):
            if key in params:
                kwargs[key] = params[key]
        if "start_time" in params:
            kwargs["start_time"] = datetime.datetime.fromisoformat(params["start_time"])
        if "end_time" in params:
            kwargs["end_time"] = datetime.datetime.fromisoformat(params["end_time"])

        await event.edit(**kwargs)
        return {"success": True, "action": "edit", "details": f"Edited event '{event.name}'."}

    async def _do_delete(self, guild: discord.Guild, params: dict) -> dict:
        event = guild.get_scheduled_event(params["event_id"])
        if not event:
            return {"success": False, "action": "delete", "details": "Event not found."}
        await event.delete()
        return {"success": True, "action": "delete", "details": f"Deleted event '{event.name}'."}
