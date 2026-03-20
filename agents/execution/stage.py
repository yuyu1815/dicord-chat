import discord

from agents.base import SingleActionExecutionAgent
from graph.state import AgentState

NAME = "stage_execution"


class StageExecutionAgent(SingleActionExecutionAgent):
    ACTION_HANDLERS: dict[str, str] = {
        "create_stage_instance": "Create stage instance",
        "edit_stage_instance": "Edit stage instance",
        "delete_stage_instance": "Delete stage instance",
        "edit_channel": "Edit stage channel",
    }

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "create_stage_instance": ["manage_channels"],
        "edit_stage_instance": ["manage_channels", "mute_members"],
        "delete_stage_instance": ["manage_channels", "mute_members"],
        "edit_channel": ["manage_channels"],
    }

    not_found_message: str = "Target not found."

    @property
    def name(self) -> str:
        return NAME

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
