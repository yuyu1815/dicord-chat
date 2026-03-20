import discord
from discord import HTTPException

from agents.base import ExecutionAgent
from graph.state import AgentState

NAME = "stage_execution"

ACTION_HANDLERS: dict[str, str] = {
    "create_stage_instance": "Create stage instance",
    "edit_stage_instance": "Edit stage instance",
    "delete_stage_instance": "Delete stage instance",
    "edit_channel": "Edit stage channel",
}


class StageExecutionAgent(ExecutionAgent):
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
            return {"success": False, "action": action_name, "details": "Target not found."}
        except HTTPException as exc:
            return {"success": False, "action": action_name, "details": f"API error: {exc.text}"}

    def _find_action(self, state: AgentState) -> str | None:
        for todo in state.get("todos", []):
            if todo.get("agent") == NAME:
                return todo.get("action")
        return None

    async def _do_create_stage_instance(self, guild: discord.Guild, params: dict) -> dict:
        channel = guild.get_channel(params["channel_id"])
        if not isinstance(channel, discord.StageChannel):
            return {"success": False, "action": "create_stage_instance", "details": "Channel is not a StageChannel."}
        instance = await channel.create_instance(topic=params.get("topic", ""))
        return {"success": True, "action": "create_stage_instance", "details": f"Created stage instance in {channel.name}."}

    async def _do_edit_stage_instance(self, guild: discord.Guild, params: dict) -> dict:
        channel = guild.get_channel(params["channel_id"])
        if not isinstance(channel, discord.StageChannel):
            return {"success": False, "action": "edit_stage_instance", "details": "Channel is not a StageChannel."}
        instance = channel.instance
        if not instance:
            return {"success": False, "action": "edit_stage_instance", "details": "No active stage instance."}
        await instance.edit(topic=params.get("topic"))
        return {"success": True, "action": "edit_stage_instance", "details": f"Updated stage instance topic in {channel.name}."}

    async def _do_delete_stage_instance(self, guild: discord.Guild, params: dict) -> dict:
        channel = guild.get_channel(params["channel_id"])
        if not isinstance(channel, discord.StageChannel):
            return {"success": False, "action": "delete_stage_instance", "details": "Channel is not a StageChannel."}
        instance = channel.instance
        if not instance:
            return {"success": False, "action": "delete_stage_instance", "details": "No active stage instance."}
        await instance.end()
        return {"success": True, "action": "delete_stage_instance", "details": f"Ended stage instance in {channel.name}."}

    async def _do_edit_channel(self, guild: discord.Guild, params: dict) -> dict:
        channel = guild.get_channel(params["channel_id"])
        if not isinstance(channel, discord.StageChannel):
            return {"success": False, "action": "edit_channel", "details": "Channel is not a StageChannel."}
        kwargs = {}
        if "name" in params:
            kwargs["name"] = params["name"]
        if "bitrate" in params:
            kwargs["bitrate"] = params["bitrate"]
        if "user_limit" in params:
            kwargs["user_limit"] = params["user_limit"]
        await channel.edit(**kwargs)
        return {"success": True, "action": "edit_channel", "details": f"Edited stage channel {channel.name}."}
