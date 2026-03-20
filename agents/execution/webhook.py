import discord
from discord import HTTPException

from agents.base import ExecutionAgent
from graph.state import AgentState

NAME = "webhook_execution"

ACTION_HANDLERS: dict[str, str] = {
    "create": "Create webhook",
    "edit": "Edit webhook",
    "delete": "Delete webhook",
    "execute": "Execute webhook",
}


class WebhookExecutionAgent(ExecutionAgent):
    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "create": ["manage_webhooks"],
        "edit": ["manage_webhooks"],
        "delete": ["manage_webhooks"],
        "execute": ["manage_webhooks"],
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
            return {"success": False, "action": action_name, "details": "Webhook or channel not found."}
        except HTTPException as exc:
            return {"success": False, "action": action_name, "details": f"API error: {exc.text}"}

    def _find_action(self, state: AgentState) -> str | None:
        for todo in state.get("todos", []):
            if todo.get("agent") == NAME and not todo.get("_blocked"):
                return todo.get("action")
        return None

    async def _do_create(self, guild: discord.Guild, params: dict) -> dict:
        channel = guild.get_channel(params["channel_id"])
        if not channel:
            return {"success": False, "action": "create", "details": "Channel not found."}

        kwargs: dict = {"name": params["name"]}
        if "avatar" in params:
            kwargs["avatar"] = params["avatar"]

        webhook = await channel.create_webhook(**kwargs)
        return {"success": True, "action": "create", "details": f"Created webhook '{webhook.name}' in {channel.name}."}

    async def _do_edit(self, guild: discord.Guild, params: dict) -> dict:
        webhook = await guild.fetch_webhook(params["webhook_id"])
        kwargs: dict = {}
        if "name" in params:
            kwargs["name"] = params["name"]
        if "channel_id" in params:
            channel = guild.get_channel(params["channel_id"])
            if channel:
                kwargs["channel"] = channel
        if "avatar" in params:
            kwargs["avatar"] = params["avatar"]

        await webhook.edit(**kwargs)
        return {"success": True, "action": "edit", "details": f"Edited webhook {params['webhook_id']}."}

    async def _do_delete(self, guild: discord.Guild, params: dict) -> dict:
        webhook = await guild.fetch_webhook(params["webhook_id"])
        await webhook.delete(reason=params.get("reason"))
        return {"success": True, "action": "delete", "details": f"Deleted webhook {params['webhook_id']}."}

    async def _do_execute(self, guild: discord.Guild, params: dict) -> dict:
        webhook = await guild.fetch_webhook(params["webhook_id"])
        kwargs: dict = {
            "content": params.get("content"),
            "username": params.get("username"),
            "avatar_url": params.get("avatar_url"),
        }
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        if "embeds" in params:
            embeds = []
            for e in params["embeds"]:
                if isinstance(e, discord.Embed):
                    embeds.append(e)
                else:
                    embeds.append(discord.Embed.from_dict(e))
            kwargs["embeds"] = embeds

        await webhook.send(**kwargs)
        return {"success": True, "action": "execute", "details": f"Executed webhook {params['webhook_id']}."}
