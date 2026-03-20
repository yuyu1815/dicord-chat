import io

import discord
from discord import HTTPException

from agents.base import ExecutionAgent
from graph.state import AgentState

NAME = "soundboard_execution"

ACTION_HANDLERS: dict[str, str] = {
    "create": "Create soundboard sound",
    "edit": "Edit soundboard sound",
    "delete": "Delete soundboard sound",
}


class SoundboardExecutionAgent(ExecutionAgent):
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
            return {"success": False, "action": action_name, "details": "Sound not found."}
        except HTTPException as exc:
            return {"success": False, "action": action_name, "details": f"API error: {exc.text}"}

    def _find_action(self, state: AgentState) -> str | None:
        for todo in state.get("todos", []):
            if todo.get("agent") == NAME:
                return todo.get("action")
        return None

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
