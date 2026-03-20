import discord

from agents.base import InvestigationAgent
from graph.state import AgentState


class AutoModInvestigationAgent(InvestigationAgent):
    """AutoModルールを調査するエージェント。"""

    @property
    def name(self) -> str:
        return "automod_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        """全AutoModルールを収集する。

        Args:
            state: ワークフロー状態。
            guild: 対象サーバー。

        Returns:
            AutoModルール情報のリスト。
        """
        rules = await guild.fetch_automod_rules()
        if not rules:
            return {"auto_moderation_rules": []}

        serialized = []
        for rule in rules:
            trigger = rule.trigger
            trigger_info = {"type": str(trigger.type)}
            if trigger.keyword_filter:
                trigger_info["keyword_filter"] = trigger.keyword_filter
            if trigger.regex_patterns:
                trigger_info["regex_patterns"] = trigger.regex_patterns
            if trigger.presets:
                trigger_info["presets"] = [str(p) for p in trigger.presets]
            if trigger.allow_list:
                trigger_info["allow_list"] = trigger.allow_list
            if trigger.mention_limit:
                trigger_info["mention_limit"] = trigger.mention_limit

            actions = []
            for action in rule.actions:
                entry = {"type": str(action.type)}
                if action.channel_id:
                    entry["channel_id"] = action.channel_id
                if action.duration:
                    entry["duration_seconds"] = action.duration
                if action.custom_message:
                    entry["custom_message"] = action.custom_message
                actions.append(entry)

            serialized.append({
                "id": rule.id,
                "name": rule.name,
                "enabled": rule.enabled,
                "event_type": str(rule.event_type),
                "trigger": trigger_info,
                "actions": actions,
                "exempt_roles": [role.name for role in rule.exempt_roles],
                "exempt_channels": [ch.name for ch in rule.exempt_channels],
            })

        return {"auto_moderation_rules": serialized}
