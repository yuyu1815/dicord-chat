import aiohttp
import discord

from agents.base import SingleActionExecutionAgent
from graph.state import AgentState
from i18n import t

NAME = "emoji_execution"


class EmojiExecutionAgent(SingleActionExecutionAgent):
    ACTION_HANDLERS: dict[str, str] = {
        "create": "Create emoji",
        "edit": "Edit emoji",
        "delete": "Delete emoji",
    }

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "create": ["manage_emojis_and_stickers"],
        "edit": ["manage_emojis_and_stickers"],
        "delete": ["manage_emojis_and_stickers"],
    }

    not_found_message: str = "Emoji not found."

    @property
    def name(self) -> str:
        return NAME

    async def _do_create(self, guild: discord.Guild, params: dict) -> dict:
        image = params.get("image")
        if isinstance(image, str):
            async with aiohttp.ClientSession() as session:
                async with session.get(image) as resp:
                    resp.raise_for_status()
                    image = await resp.read()

        kwargs: dict = {"name": params["name"], "image": image}
        if "roles" in params:
            roles = [guild.get_role(r) for r in params["roles"]]
            kwargs["roles"] = [r for r in roles if r is not None]

        emoji = await guild.create_custom_emoji(**kwargs)
        return {"success": True, "action": "create", "details": t("exec.emoji.created", locale=self._locale, name=emoji.name)}

    async def _do_edit(self, guild: discord.Guild, params: dict) -> dict:
        emoji = guild.get_emoji(params["emoji_id"])
        if not emoji:
            return {"success": False, "action": "edit", "details": t("exec.emoji.not_found", locale=self._locale)}

        kwargs: dict = {}
        if "name" in params:
            kwargs["name"] = params["name"]
        if "roles" in params:
            roles = [guild.get_role(r) for r in params["roles"]]
            kwargs["roles"] = [r for r in roles if r is not None]

        await emoji.edit(**kwargs)
        return {"success": True, "action": "edit", "details": t("exec.emoji.edited", locale=self._locale, name=emoji.name)}

    async def _do_delete(self, guild: discord.Guild, params: dict) -> dict:
        emoji = guild.get_emoji(params["emoji_id"])
        if not emoji:
            return {"success": False, "action": "delete", "details": t("exec.emoji.not_found", locale=self._locale)}
        await emoji.delete()
        return {"success": True, "action": "delete", "details": t("exec.emoji.deleted", locale=self._locale, name=emoji.name)}
