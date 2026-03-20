import datetime

import discord

from agents.base import SingleActionExecutionAgent
from graph.state import AgentState

NAME = "automod_execution"


def _build_trigger(trigger_type: str, metadata: dict | None) -> discord.AutoModTrigger:
    kwargs: dict = {"type": _build_trigger_type(trigger_type)}
    if metadata:
        if "keyword_filter" in metadata:
            kwargs["keyword_filter"] = metadata["keyword_filter"]
        if "regex_patterns" in metadata:
            kwargs["regex_patterns"] = metadata["regex_patterns"]
        if "presets" in metadata:
            kwargs["presets"] = [discord.AutoModPresets(p) for p in metadata["presets"]]
        if "allow_list" in metadata:
            kwargs["allow_list"] = metadata["allow_list"]
        if "mention_total_limit" in metadata:
            kwargs["mention_limit"] = metadata["mention_total_limit"]
    return discord.AutoModTrigger(**kwargs)


def _build_trigger_type(trigger_type: str) -> discord.AutoModRuleTriggerType:
    type_map = {
        "keyword": discord.AutoModRuleTriggerType.keyword,
        "harmful_link": discord.AutoModRuleTriggerType.harmful_link,
        "spam": discord.AutoModRuleTriggerType.spam,
        "keyword_preset": discord.AutoModRuleTriggerType.keyword_preset,
        "mention_spam": discord.AutoModRuleTriggerType.mention_spam,
    }
    return type_map.get(trigger_type, discord.AutoModRuleTriggerType.keyword)


def _build_actions(actions: list[dict] | None) -> list[discord.AutoModRuleAction]:
    if not actions:
        return []
    type_map = {
        "block_message": discord.AutoModRuleActionType.block_message,
        "send_alert_message": discord.AutoModRuleActionType.send_alert_message,
        "timeout": discord.AutoModRuleActionType.timeout,
    }
    result = []
    for a in actions:
        action_type = type_map.get(a.get("type", "block_message"), discord.AutoModRuleActionType.block_message)
        kwargs: dict = {"type": action_type}
        if "channel_id" in a:
            kwargs["channel_id"] = a["channel_id"]
        if "duration" in a:
            kwargs["duration"] = datetime.timedelta(seconds=a["duration"])
        result.append(discord.AutoModRuleAction(**kwargs))
    return result


class AutoModExecutionAgent(SingleActionExecutionAgent):
    ACTION_HANDLERS: dict[str, str] = {
        "create_rule": "Create AutoMod rule",
        "edit_rule": "Edit AutoMod rule",
        "delete_rule": "Delete AutoMod rule",
    }

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "create_rule": ["manage_guild"],
        "edit_rule": ["manage_guild"],
        "delete_rule": ["manage_guild"],
    }

    not_found_message: str = "Rule not found."

    @property
    def name(self) -> str:
        return NAME

    async def _do_create_rule(self, guild: discord.Guild, params: dict) -> dict:
        trigger = _build_trigger(params.get("trigger_type", "keyword"), params.get("trigger_metadata"))
        actions = _build_actions(params.get("actions"))

        kwargs: dict = {
            "name": params["name"],
            "trigger": trigger,
            "actions": actions,
            "enabled": params.get("enabled", True),
        }
        if "exempt_roles" in params:
            kwargs["exempt_roles"] = params["exempt_roles"]
        if "exempt_channels" in params:
            kwargs["exempt_channels"] = params["exempt_channels"]

        rule = await guild.create_automod_rule(**kwargs)
        return {"success": True, "action": "create_rule", "details": f"Created AutoMod rule '{rule.name}'."}

    async def _do_edit_rule(self, guild: discord.Guild, params: dict) -> dict:
        kwargs: dict = {}
        if "name" in params:
            kwargs["name"] = params["name"]
        if "trigger_type" in params:
            kwargs["trigger_type"] = _build_trigger_type(params["trigger_type"])
        if "actions" in params:
            kwargs["actions"] = _build_actions(params["actions"])
        if "enabled" in params:
            kwargs["enabled"] = params["enabled"]

        rule = await guild.edit_automod_rule(params["rule_id"], **kwargs)
        return {"success": True, "action": "edit_rule", "details": f"Edited AutoMod rule '{rule.name}'."}

    async def _do_delete_rule(self, guild: discord.Guild, params: dict) -> dict:
        await guild.delete_automod_rule(params["rule_id"])
        return {"success": True, "action": "delete_rule", "details": f"Deleted AutoMod rule {params['rule_id']}."}
