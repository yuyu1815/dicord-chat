import discord
from discord import HTTPException

from agents.base import ExecutionAgent
from graph.state import AgentState

NAME = "automod_execution"

ACTION_HANDLERS: dict[str, str] = {
    "create_rule": "Create AutoMod rule",
    "edit_rule": "Edit AutoMod rule",
    "delete_rule": "Delete AutoMod rule",
}


def _build_trigger_metadata(trigger_type: str, metadata: dict | None) -> discord.AutoModTriggerMetadata:
    if not metadata:
        return discord.AutoModTriggerMetadata()

    keyword_filter = metadata.get("keyword_filter")
    regex_patterns = metadata.get("regex_patterns")
    presets = metadata.get("presets")
    allow_list = metadata.get("allow_list")
    mention_total_limit = metadata.get("mention_total_limit")

    return discord.AutoModTriggerMetadata(
        keyword_filter=keyword_filter,
        regex_patterns=regex_patterns,
        presets=[discord.AutoModPresetsType(p) for p in presets] if presets else None,
        allow_list=allow_list,
        mention_total_limit=mention_total_limit,
    )


def _build_trigger_type(trigger_type: str) -> discord.AutoModTriggerType:
    type_map = {
        "keyword": discord.AutoModTriggerType.keyword,
        "harmful_link": discord.AutoModTriggerType.harmful_link,
        "spam": discord.AutoModTriggerType.spam,
        "keyword_preset": discord.AutoModTriggerType.keyword_preset,
        "mention_spam": discord.AutoModTriggerType.mention_spam,
    }
    return type_map.get(trigger_type, discord.AutoModTriggerType.keyword)


def _build_actions(actions: list[dict] | None) -> list[discord.AutoModAction]:
    if not actions:
        return []
    type_map = {
        "block_message": discord.AutoModActionType.block_message,
        "send_alert_message": discord.AutoModActionType.send_alert_message,
        "timeout": discord.AutoModActionType.timeout,
    }
    result = []
    for a in actions:
        action_type = type_map.get(a.get("type", "block_message"), discord.AutoModActionType.block_message)
        kwargs: dict = {"type": action_type}
        if "channel_id" in a:
            kwargs["channel_id"] = a["channel_id"]
        if "duration" in a:
            kwargs["duration"] = a["duration"]
        result.append(discord.AutoModAction(**kwargs))
    return result


class AutoModExecutionAgent(ExecutionAgent):
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
            return {"success": False, "action": action_name, "details": "Rule not found."}
        except HTTPException as exc:
            return {"success": False, "action": action_name, "details": f"API error: {exc.text}"}

    def _find_action(self, state: AgentState) -> str | None:
        for todo in state.get("todos", []):
            if todo.get("agent") == NAME:
                return todo.get("action")
        return None

    async def _do_create_rule(self, guild: discord.Guild, params: dict) -> dict:
        trigger_type = _build_trigger_type(params.get("trigger_type", "keyword"))
        metadata = _build_trigger_metadata(params.get("trigger_type"), params.get("trigger_metadata"))
        actions = _build_actions(params.get("actions"))

        kwargs: dict = {
            "name": params["name"],
            "trigger_type": trigger_type,
            "trigger_metadata": metadata,
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
