import discord
from discord import HTTPException

from agents.base import ExecutionAgent, _find_action
from graph.state import AgentState

NAME = "emoji_execution"

ACTION_HANDLERS: dict[str, str] = {
    "create": "Create emoji",
    "edit": "Edit emoji",
    "delete": "Delete emoji",
}


class EmojiExecutionAgent(ExecutionAgent):
    single_action: bool = True

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "create": ["manage_emojis_and_stickers"],
        "edit": ["manage_emojis_and_stickers"],
        "delete": ["manage_emojis_and_stickers"],
    }

    @property
    def name(self) -> str:
        return NAME

    async def execute(self, state: AgentState, guild: discord.Guild) -> dict:
        action_name = _find_action(state, NAME)
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
            return {"success": False, "action": action_name, "details": "Emoji not found."}
        except HTTPException as exc:
            return {"success": False, "action": action_name, "details": f"API error: {exc.text}"}

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
