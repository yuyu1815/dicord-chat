import datetime

import discord

from agents.base import SingleActionExecutionAgent
from graph.state import AgentState
from i18n import t

NAME = "event_execution"


class EventExecutionAgent(SingleActionExecutionAgent):
    ACTION_HANDLERS: dict[str, str] = {
        "create": "Create scheduled event",
        "edit": "Edit scheduled event",
        "delete": "Delete scheduled event",
    }

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "create": ["manage_events"],
        "edit": ["manage_events"],
        "delete": ["manage_events"],
    }

    not_found_message: str = "Event not found."

    @property
    def name(self) -> str:
        return NAME

    def _parse_event_status(self, raw: str | None) -> discord.EventStatus:
        status_map = {
            "scheduled": discord.EventStatus.scheduled,
            "active": discord.EventStatus.active,
            "completed": discord.EventStatus.completed,
            "canceled": discord.EventStatus.canceled,
        }
        return status_map.get(raw, discord.EventStatus.scheduled)

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
            "privacy_level": discord.PrivacyLevel.guild_only,
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
        return {"success": True, "action": "create", "details": t("exec.event.created", locale=self._locale, name=event.name)}

    async def _do_edit(self, guild: discord.Guild, params: dict) -> dict:
        event = guild.get_scheduled_event(params["event_id"])
        if not event:
            return {"success": False, "action": "edit", "details": t("exec.event.not_found", locale=self._locale)}

        kwargs: dict = {}
        if "name" in params:
            kwargs["name"] = params["name"]
        if "description" in params:
            kwargs["description"] = params["description"]
        if "status" in params:
            kwargs["status"] = self._parse_event_status(params["status"])
        if "start_time" in params:
            kwargs["start_time"] = datetime.datetime.fromisoformat(params["start_time"])
        if "end_time" in params:
            kwargs["end_time"] = datetime.datetime.fromisoformat(params["end_time"])

        await event.edit(**kwargs)
        return {"success": True, "action": "edit", "details": t("exec.event.edited", locale=self._locale, name=event.name)}

    async def _do_delete(self, guild: discord.Guild, params: dict) -> dict:
        event = guild.get_scheduled_event(params["event_id"])
        if not event:
            return {"success": False, "action": "delete", "details": t("exec.event.not_found", locale=self._locale)}
        await event.delete()
        return {"success": True, "action": "delete", "details": t("exec.event.deleted", locale=self._locale, name=event.name)}
