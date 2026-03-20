import discord

from agents.base import InvestigationAgent
from graph.state import AgentState

MAX_TOPIC_LENGTH = 200


class ChannelInvestigationAgent(InvestigationAgent):
    """チャンネル情報を調査するエージェント。"""

    @property
    def name(self) -> str:
        return "channel_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        """テキスト・ボイス・ステージチャンネルの情報を収集する。

        Args:
            state: ワークフロー状態。
            guild: 対象サーバー。

        Returns:
            チャンネルタイプ別の情報を含む辞書。
        """
        def _channel_info(ch: discord.abc.GuildChannel) -> dict:
            base = {
                "id": ch.id,
                "name": ch.name,
                "type": str(ch.type),
                "category": ch.category.name if ch.category else None,
                "position": ch.position,
                "nsfw": getattr(ch, "nsfw", False),
            }
            topic = getattr(ch, "topic", None)
            base["topic"] = (topic[:MAX_TOPIC_LENGTH] if topic and len(topic) > MAX_TOPIC_LENGTH else topic)
            base["permissions_synced"] = ch.permissions_synced
            return base

        text_channels = [_channel_info(ch) for ch in guild.text_channels]
        voice_channels = [_channel_info(ch) for ch in guild.voice_channels]
        stage_channels = [_channel_info(ch) for ch in guild.stage_channels]

        return {
            "text_channels": text_channels,
            "voice_channels": voice_channels,
            "stage_channels": stage_channels,
            "total_count": len(text_channels) + len(voice_channels) + len(stage_channels),
        }
