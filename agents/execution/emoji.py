import discord

from agents.base import SingleActionExecutionAgent
from graph.state import AgentState

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
            image = await discord.Preview.from_url(image).read()

        kwargs: dict = {"name": params["name"], "image": image}
        if "roles" in params:
            roles = [guild.get_role(r) for r in params["roles"]]
            kwargs["roles"] = [r for r in roles if r is not None]

        emoji = await guild.create_custom_emoji(**kwargs)
        return {"success": True, "action": "create", "details": f"Created emoji '{emoji.name}'."}

    async def _do_edit(self, guild: discord.Guild, params: dict) -> dict:
        emoji = guild.get_emoji(params["emoji_id"])
        if not emoji:
            return {"success": False, "action": "edit", "details": "Emoji not found."}

        kwargs: dict = {}
        if "name" in params:
            kwargs["name"] = params["name"]
        if "roles" in params:
            roles = [guild.get_role(r) for r in params["roles"]]
            kwargs["roles"] = [r for r in roles if r is not None]

        await emoji.edit(**kwargs)
        return {"success": True, "action": "edit", "details": f"Edited emoji '{emoji.name}'."}

    async def _do_delete(self, guild: discord.Guild, params: dict) -> dict:
        emoji = guild.get_emoji(params["emoji_id"])
        if not emoji:
            return {"success": False, "action": "delete", "details": "Emoji not found."}
        await emoji.delete()
        return {"success": True, "action": "delete", "details": f"Deleted emoji '{emoji.name}'."}
