import discord

from agents.base import InvestigationAgent
from graph.state import AgentState


class SoundboardInvestigationAgent(InvestigationAgent):
    """サウンドボードを調査するエージェント。"""

    @property
    def name(self) -> str:
        return "soundboard_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        """全サウンドボードサウンドを収集する。

        Args:
            state: ワークフロー状態。
            guild: 対象サーバー。

        Returns:
            サウンド情報のリスト。
        """
        sounds = guild.soundboard_sounds
        if not sounds:
            return {"soundboard_sounds": []}

        serialized = []
        for sound in sounds:
            creator_name = None
            if hasattr(sound, "user") and sound.user:
                creator_name = sound.user.display_name

            serialized.append({
                "id": sound.id,
                "name": sound.name,
                "emoji": sound.emoji,
                "volume": sound.volume,
                "available": sound.available,
                "creator": creator_name,
                "guild_id": sound.guild_id,
            })

        return {"soundboard_sounds": serialized}
