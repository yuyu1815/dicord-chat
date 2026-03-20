import discord

from agents.base import InvestigationAgent
from graph.state import AgentState


class ForumInvestigationAgent(InvestigationAgent):
    @property
    def name(self) -> str:
        return "forum_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        forums = [
            {
                "id": forum.id,
                "name": forum.name,
                "topic": forum.topic,
                "tags": [
                    {
                        "id": tag.id,
                        "name": tag.name,
                        "emoji": str(tag.emoji) if tag.emoji else None,
                        "moderated": tag.moderated,
                    }
                    for tag in forum.available_tags
                ],
            }
            for forum in guild.channels
            if isinstance(forum, discord.ForumChannel)
        ]
        return {"forums": forums, "total_count": len(forums)}
