import discord

from agents.base import InvestigationAgent
from graph.state import AgentState


class CategoryInvestigationAgent(InvestigationAgent):
    @property
    def name(self) -> str:
        return "category_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        categories = [
            {
                "id": cat.id,
                "name": cat.name,
                "position": cat.position,
                "channel_count": len(cat.channels),
                "channels": [ch.name for ch in cat.channels],
            }
            for cat in guild.categories
        ]
        return {"categories": categories, "total_count": len(categories)}
