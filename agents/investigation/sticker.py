import discord

from agents.base import InvestigationAgent
from graph.state import AgentState


class StickerInvestigationAgent(InvestigationAgent):
    """カスタムスタンプを調査するエージェント。"""

    @property
    def name(self) -> str:
        return "sticker_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        """全カスタムスタンプを収集する。

        Args:
            state: ワークフロー状態。
            guild: 対象サーバー。

        Returns:
            スタンプ情報のリスト。
        """
        if not guild.stickers:
            return {"stickers": [], "total_count": 0}

        serialized = []
        for sticker in guild.stickers:
            serialized.append({
                "id": sticker.id,
                "name": sticker.name,
                "description": sticker.description,
                "format_type": str(sticker.format),
                "tags": sticker.tags,
                "available": sticker.available,
                "created_at": sticker.created_at.isoformat() if sticker.created_at else None,
                "pack_name": sticker.pack_id,
            })

        return {"stickers": serialized, "total_count": len(serialized)}
