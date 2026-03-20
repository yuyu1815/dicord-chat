import discord

from agents.base import SingleActionExecutionAgent
from graph.state import AgentState
from i18n import t

NAME = "invite_execution"


class InviteExecutionAgent(SingleActionExecutionAgent):
    ACTION_HANDLERS: dict[str, str] = {
        "create": "Create invite",
        "delete": "Delete invite",
    }

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "create": ["create_invite"],
        "delete": ["manage_channels"],
    }

    not_found_message: str = "Invite or channel not found."

    @property
    def name(self) -> str:
        return NAME

    async def _do_create(self, guild: discord.Guild, params: dict) -> dict:
        channel_id = params.get("channel_id")
        if not channel_id:
            if guild.system_channel:
                channel_id = guild.system_channel.id
            elif guild.text_channels:
                channel_id = guild.text_channels[0].id
            else:
                return {"success": False, "action": "create", "details": t("exec.invite.no_channel", locale=self._locale)}

        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "create", "details": t("exec.invite.channel_not_found", locale=self._locale)}

        kwargs: dict = {
            "max_uses": params.get("max_uses"),
            "max_age": params.get("max_age"),
            "temporary": params.get("temporary", False),
            "unique": params.get("unique", False),
            "reason": params.get("reason"),
        }
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        invite = await channel.create_invite(**kwargs)
        return {"success": True, "action": "create", "details": t("exec.invite.created", locale=self._locale, url=invite.url)}

    async def _do_delete(self, guild: discord.Guild, params: dict) -> dict:
        invite = await guild.fetch_invite(params["invite_code"])
        await invite.delete(reason=params.get("reason"))
        return {"success": True, "action": "delete", "details": t("exec.invite.deleted", locale=self._locale, code=params['invite_code'])}
