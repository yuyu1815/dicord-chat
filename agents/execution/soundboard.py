import io

import discord

from agents.base import SingleActionExecutionAgent
from graph.state import AgentState

NAME = "soundboard_execution"


class SoundboardExecutionAgent(SingleActionExecutionAgent):
    ACTION_HANDLERS: dict[str, str] = {
        "create": "Create soundboard sound",
        "edit": "Edit soundboard sound",
        "delete": "Delete soundboard sound",
    }

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "create": ["manage_expressions"],
        "edit": ["manage_expressions"],
        "delete": ["manage_expressions"],
    }

    not_found_message: str = "Sound not found."

    @property
    def name(self) -> str:
        return NAME

    def _resolve_sound(self, data: bytes | None) -> io.IOBase:
        if data is None:
            raise ValueError("Sound data is required.")
        return io.BytesIO(data)

    async def _do_create(self, guild: discord.Guild, params: dict) -> dict:
        sound = self._resolve_sound(params.get("sound"))

        kwargs: dict = {
            "name": params["name"],
            "sound": sound,
        }
        if "emoji" in params:
            kwargs["emoji"] = params["emoji"]
        if "volume" in params:
            kwargs["volume"] = params["volume"]

        created = await guild.create_soundboard_sound(**kwargs)
        return {"success": True, "action": "create", "details": f"Created soundboard sound '{created.name}'."}

    async def _do_edit(self, guild: discord.Guild, params: dict) -> dict:
        sound = guild.get_soundboard_sound(params["sound_id"])
        if not sound:
            return {"success": False, "action": "edit", "details": "Sound not found."}

        kwargs: dict = {}
        if "name" in params:
            kwargs["name"] = params["name"]
        if "emoji" in params:
            kwargs["emoji"] = params["emoji"]
        if "volume" in params:
            kwargs["volume"] = params["volume"]

        await sound.edit(**kwargs)
        return {"success": True, "action": "edit", "details": f"Edited soundboard sound '{sound.name}'."}

    async def _do_delete(self, guild: discord.Guild, params: dict) -> dict:
        sound = guild.get_soundboard_sound(params["sound_id"])
        if not sound:
            return {"success": False, "action": "delete", "details": "Sound not found."}
        await sound.delete()
        return {"success": True, "action": "delete", "details": f"Deleted soundboard sound '{sound.name}'."}
