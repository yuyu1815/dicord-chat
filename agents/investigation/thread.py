import discord

from agents.base import InvestigationAgent
from graph.state import AgentState


class ThreadInvestigationAgent(InvestigationAgent):
    """スレッド情報を調査するエージェント。"""

    @property
    def name(self) -> str:
        return "thread_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        """全スレッドの情報を収集する。

        Args:
            state: ワークフロー状態。
            guild: 対象サーバー。

        Returns:
            スレッド情報のリストと総数。
        """
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
