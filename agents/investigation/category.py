import discord

from agents.base import InvestigationAgent
from graph.state import AgentState


class CategoryInvestigationAgent(InvestigationAgent):
    """カテゴリ情報を調査するエージェント。"""

    @property
    def name(self) -> str:
        return "category_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        """全カテゴリと配下チャンネルの一覧を収集する。

        Args:
            state: ワークフロー状態。
            guild: 対象サーバー。

        Returns:
            カテゴリ情報のリストと総数。
        """
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
