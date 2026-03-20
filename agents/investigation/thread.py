import discord

from agents.base import InvestigationAgent
from graph.state import AgentState


class ThreadInvestigationAgent(InvestigationAgent):
    @property
    def name(self) -> str:
        return "thread_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        threads = [
            {
                "id": thread.id,
                "name": thread.name,
                "parent_channel": thread.parent.name if thread.parent else None,
                "owner": thread.owner.name if thread.owner else None,
                "member_count": thread.member_count,
                "archived": thread.archived,
                "locked": thread.locked,
                "created_at": thread.created_at.isoformat(),
            }
            for thread in guild.threads
        ]
        return {"threads": threads, "total_count": len(threads)}
