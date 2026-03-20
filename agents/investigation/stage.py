import discord

from agents.base import InvestigationAgent
from graph.state import AgentState


class StageInvestigationAgent(InvestigationAgent):
    """ステージチャンネルを調査するエージェント。"""

    @property
    def name(self) -> str:
        return "stage_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        """全ステージチャンネルとそのステージインスタンスを収集する。

        Args:
            state: ワークフロー状態。
            guild: 対象サーバー。

        Returns:
            ステージ情報のリスト。
        """
        if not guild.stage_channels:
            return {"stages": [], "total_count": 0}

        stages = []
        for channel in guild.stage_channels:
            stage_instance = channel.instance
            members = []
            if channel.members:
                members = [m.display_name for m in channel.members]

            stage_info = {
                "id": channel.id,
                "name": channel.name,
                "topic": channel.topic or None,
                "category": channel.category.name if channel.category else None,
                "bitrate": channel.bitrate,
                "current_members": members,
                "stage_instance_active": stage_instance is not None,
            }

            if stage_instance:
                stage_info["speaker_count"] = len(stage_instance.speakers) if stage_instance.speakers else 0
                stage_info["topic"] = stage_instance.topic

            stages.append(stage_info)

        return {"stages": stages, "total_count": len(stages)}
