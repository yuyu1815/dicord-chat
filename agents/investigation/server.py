import discord

from agents.base import InvestigationAgent
from graph.state import AgentState


class ServerInvestigationAgent(InvestigationAgent):
    @property
    def name(self) -> str:
        return "server_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        return {
            "name": guild.name,
            "id": guild.id,
            "owner_id": guild.owner_id,
            "member_count": guild.member_count,
            "created_at": guild.created_at.isoformat(),
            "verification_level": str(guild.verification_level),
            "icon_url": guild.icon.url if guild.icon else None,
            "banner_url": guild.banner.url if guild.banner else None,
            "description": guild.description,
            "features": guild.features,
            "system_channel": guild.system_channel.name if guild.system_channel else None,
            "rules_channel": guild.rules_channel.name if guild.rules_channel else None,
            "max_members": guild.max_members,
            "premium_tier": guild.premium_tier,
            "nsfw_level": str(guild.nsfw_level),
        }
