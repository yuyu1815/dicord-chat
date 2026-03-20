import discord
from discord import HTTPException

from agents.base import ExecutionAgent, _find_action
from graph.state import AgentState

NAME = "invite_execution"

ACTION_HANDLERS: dict[str, str] = {
    "create": "Create invite",
    "delete": "Delete invite",
}


class InviteExecutionAgent(ExecutionAgent):
    single_action: bool = True

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "create": ["create_invite"],
        "delete": ["manage_channels"],
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
            return {"success": False, "action": action_name, "details": "Invite or channel not found."}
        except HTTPException as exc:
            return {"success": False, "action": action_name, "details": f"API error: {exc.text}"}

    async def _do_create(self, guild: discord.Guild, params: dict) -> dict:
        channel_id = params.get("channel_id")
        if not channel_id:
            if guild.system_channel:
                channel_id = guild.system_channel.id
            elif guild.text_channels:
                channel_id = guild.text_channels[0].id
            else:
                return {"success": False, "action": "create", "details": "No channel available."}

        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "create", "details": "Channel not found."}

        kwargs: dict = {
            "max_uses": params.get("max_uses"),
            "max_age": params.get("max_age"),
            "temporary": params.get("temporary", False),
            "unique": params.get("unique", False),
            "reason": params.get("reason"),
        }
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        invite = await channel.create_invite(**kwargs)
        return {"success": True, "action": "create", "details": f"Created invite: {invite.url}"}

    async def _do_delete(self, guild: discord.Guild, params: dict) -> dict:
        invite = await guild.fetch_invite(params["invite_code"])
        await invite.delete(reason=params.get("reason"))
        return {"success": True, "action": "delete", "details": f"Deleted invite {params['invite_code']}."}
