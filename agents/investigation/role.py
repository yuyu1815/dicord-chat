import discord

from agents.base import InvestigationAgent
from graph.state import AgentState

KEY_PERMISSIONS = [
    "administrator",
    "manage_guild",
    "manage_channels",
    "kick_members",
    "ban_members",
    "mention_everyone",
    "hoist",
]


class RoleInvestigationAgent(InvestigationAgent):
    @property
    def name(self) -> str:
        return "role_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        roles = []
        for role in guild.roles:
            perms = role.permissions
            key_perms = {perm: getattr(perms, perm, False) for perm in KEY_PERMISSIONS}
            roles.append({
                "id": role.id,
                "name": role.name,
                "color": str(role.color),
                "position": role.position,
                "mentionable": role.mentionable,
                "managed": role.managed,
                "permissions": key_perms,
                "member_count": len(role.members),
            })

        return {
            "roles": roles,
            "total_count": len(roles),
        }
