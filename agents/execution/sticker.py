import io

import discord
from discord import HTTPException

from agents.base import ExecutionAgent
from graph.state import AgentState

NAME = "sticker_execution"

ACTION_HANDLERS: dict[str, str] = {
    "create": "Create sticker",
    "edit": "Edit sticker",
    "delete": "Delete sticker",
}

FORMAT_MAP: dict[str, int] = {
    "png": 1,
    "apng": 2,
    "lottie": 3,
    "gif": 4,
}


class StickerExecutionAgent(ExecutionAgent):
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
            return {"success": False, "action": action_name, "details": "Sticker not found."}
        except HTTPException as exc:
            return {"success": False, "action": action_name, "details": f"API error: {exc.text}"}

    def _find_action(self, state: AgentState) -> str | None:
        for todo in state.get("todos", []):
            if todo.get("agent") == NAME:
                return todo.get("action")
        return None

    def _resolve_file(self, data: bytes | None) -> io.IOBase:
        if data is None:
            raise ValueError("Sticker file data is required.")
        return io.BytesIO(data)

    def _resolve_format(self, raw: str | None) -> int:
        if raw is None:
            return 1  # PNG default
        return FORMAT_MAP.get(raw, 1)

    async def _do_create(self, guild: discord.Guild, params: dict) -> dict:
        file = self._resolve_file(params.get("file"))
        format_type = self._resolve_format(params.get("format_type"))

        kwargs: dict = {
            "name": params["name"],
            "description": params.get("description", ""),
            "file": file,
            "format_type": format_type,
        }
        if "tags" in params:
            kwargs["tags"] = params["tags"]

        sticker = await guild.create_sticker(**kwargs)
        return {"success": True, "action": "create", "details": f"Created sticker '{sticker.name}'."}

    async def _do_edit(self, guild: discord.Guild, params: dict) -> dict:
        sticker = guild.get_sticker(params["sticker_id"])
        if not sticker:
            return {"success": False, "action": "edit", "details": "Sticker not found."}

        kwargs: dict = {}
        if "name" in params:
            kwargs["name"] = params["name"]
        if "description" in params:
            kwargs["description"] = params["description"]
        if "tags" in params:
            kwargs["tags"] = params["tags"]

        await sticker.edit(**kwargs)
        return {"success": True, "action": "edit", "details": f"Edited sticker '{sticker.name}'."}

    async def _do_delete(self, guild: discord.Guild, params: dict) -> dict:
        sticker = guild.get_sticker(params["sticker_id"])
        if not sticker:
            return {"success": False, "action": "delete", "details": "Sticker not found."}
        await sticker.delete()
        return {"success": True, "action": "delete", "details": f"Deleted sticker '{sticker.name}'."}
