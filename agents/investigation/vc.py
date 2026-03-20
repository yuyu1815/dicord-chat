import discord

from agents.base import InvestigationAgent
from graph.state import AgentState


class VCInvestigationAgent(InvestigationAgent):
    """ボイスチャンネルを調査するエージェント。"""

    @property
    def name(self) -> str:
        return "vc_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        """全ボイスチャンネルと参加メンバーの状態を収集する。

        Args:
            state: ワークフロー状態。
            guild: 対象サーバー。

        Returns:
            ボイスチャンネル情報のリストと総数。
        """
        channels = []
        for vc in guild.voice_channels:
            current_members = [
                {
                    "name": member.display_name,
                    "muted": member.voice.mute if member.voice else False,
                    "deafened": member.voice.deaf if member.voice else False,
                    "self_muted": member.voice.self_mute if member.voice else False,
                    "self_deafened": member.voice.self_deaf if member.voice else False,
                    "streaming": member.voice.self_stream if member.voice else False,
                }
                for member in vc.members
            ]

            channels.append({
                "id": vc.id,
                "name": vc.name,
                "category": vc.category.name if vc.category else None,
                "position": vc.position,
                "bitrate": vc.bitrate,
                "user_limit": vc.user_limit,
                "current_members": current_members,
                "member_count": len(vc.members),
                "nsfw": vc.nsfw,
                "permissions_synced": vc.permissions_synced,
                "status": vc.status if hasattr(vc, "status") else None,
            })

        return {"voice_channels": channels, "total_count": len(channels)}
