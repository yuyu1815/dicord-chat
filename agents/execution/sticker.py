import io

import discord

from agents.base import SingleActionExecutionAgent
from graph.state import AgentState
from i18n import t

NAME = "sticker_execution"

class StickerExecutionAgent(SingleActionExecutionAgent):
    # Sticker操作はEmojiと同様にギルド単位のレート制限がある
    ACTION_COOLDOWN: float = 15.0

    ACTION_HANDLERS: dict[str, str] = {
        "create": "Create sticker",
        "edit": "Edit sticker",
        "delete": "Delete sticker",
    }

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "create": ["manage_emojis_and_stickers"],
        "edit": ["manage_emojis_and_stickers"],
        "delete": ["manage_emojis_and_stickers"],
    }

    not_found_message: str = "Sticker not found."

    @property
    def name(self) -> str:
        return NAME

    def _resolve_file(self, data: bytes | None) -> io.IOBase:
        if data is None:
            raise ValueError(t("exec.sticker.data_required", locale=self._locale))
        return io.BytesIO(data)

    async def _do_create(self, guild: discord.Guild, params: dict) -> dict:
        file = self._resolve_file(params.get("file"))

        kwargs: dict = {
            "name": params["name"],
            "description": params.get("description", ""),
            "emoji": params.get("tags", params.get("emoji", "\U0001f4a9")),
            "file": file,
        }

        sticker = await guild.create_sticker(**kwargs)
        return {"success": True, "action": "create", "details": t("exec.sticker.created", locale=self._locale, name=sticker.name)}

    async def _do_edit(self, guild: discord.Guild, params: dict) -> dict:
        sticker = guild.get_sticker(params["sticker_id"])
        if not sticker:
            return {"success": False, "action": "edit", "details": t("exec.sticker.not_found", locale=self._locale)}

        kwargs: dict = {}
        if "name" in params:
            kwargs["name"] = params["name"]
        if "description" in params:
            kwargs["description"] = params["description"]
        if "tags" in params:
            kwargs["emoji"] = params["tags"]
        elif "emoji" in params:
            kwargs["emoji"] = params["emoji"]

        await sticker.edit(**kwargs)
        return {"success": True, "action": "edit", "details": t("exec.sticker.edited", locale=self._locale, name=sticker.name)}

    async def _do_delete(self, guild: discord.Guild, params: dict) -> dict:
        sticker = guild.get_sticker(params["sticker_id"])
        if not sticker:
            return {"success": False, "action": "delete", "details": t("exec.sticker.not_found", locale=self._locale)}
        await sticker.delete()
        return {"success": True, "action": "delete", "details": t("exec.sticker.deleted", locale=self._locale, name=sticker.name)}
