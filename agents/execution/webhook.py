import discord

from agents.base import SingleActionExecutionAgent
from graph.state import AgentState
from i18n import t

NAME = "webhook_execution"


class WebhookExecutionAgent(SingleActionExecutionAgent):
    ACTION_HANDLERS: dict[str, str] = {
        "create": "Create webhook",
        "edit": "Edit webhook",
        "delete": "Delete webhook",
        "execute": "Execute webhook",
    }

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "create": ["manage_webhooks"],
        "edit": ["manage_webhooks"],
        "delete": ["manage_webhooks"],
        "execute": ["manage_webhooks"],
    }

    not_found_message: str = "Webhook or channel not found."

    @property
    def name(self) -> str:
        return NAME

    async def _do_create(self, guild: discord.Guild, params: dict) -> dict:
        channel = guild.get_channel(params["channel_id"])
        if not channel:
            return {"success": False, "action": "create", "details": t("exec.webhook.channel_not_found", locale=self._locale)}

        kwargs: dict = {"name": params["name"]}
        if "avatar" in params:
            kwargs["avatar"] = params["avatar"]

        webhook = await channel.create_webhook(**kwargs)
        return {"success": True, "action": "create", "details": t("exec.webhook.created", locale=self._locale, name=webhook.name, channel=channel.name)}

    async def _do_edit(self, guild: discord.Guild, params: dict) -> dict:
        webhook = await self._bot.fetch_webhook(params["webhook_id"])
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
        return {"success": True, "action": "edit", "details": t("exec.webhook.edited", locale=self._locale, id=params['webhook_id'])}

    async def _do_delete(self, guild: discord.Guild, params: dict) -> dict:
        webhook = await self._bot.fetch_webhook(params["webhook_id"])
        await webhook.delete(reason=params.get("reason"))
        return {"success": True, "action": "delete", "details": t("exec.webhook.deleted", locale=self._locale, id=params['webhook_id'])}

    async def _do_execute(self, guild: discord.Guild, params: dict) -> dict:
        webhook = await self._bot.fetch_webhook(params["webhook_id"])
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

        files = []
        for file_info in params.get("files", []):
            if isinstance(file_info, str):
                files.append(discord.File(file_info))
            elif isinstance(file_info, dict):
                files.append(discord.File(file_info["path"], filename=file_info.get("filename")))
        if files:
            kwargs["files"] = files

        await webhook.send(**kwargs)
        return {"success": True, "action": "execute", "details": t("exec.webhook.executed", locale=self._locale, id=params['webhook_id'])}
