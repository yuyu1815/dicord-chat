import discord

from agents.base import InvestigationAgent
from graph.state import AgentState


class EmojiInvestigationAgent(InvestigationAgent):
    @property
    def name(self) -> str:
        return "emoji_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        if not guild.emojis:
            return {"emojis": []}

        serialized = []
        for emoji in guild.emojis:
            creator_name = None
            if emoji.user:
                creator_name = emoji.user.display_name

            serialized.append({
                "id": emoji.id,
                "name": emoji.name,
                "animated": emoji.animated,
                "managed": emoji.managed,
                "roles": [role.name for role in emoji.roles],
                "creator": creator_name,
            })

        return {"emojis": serialized}
