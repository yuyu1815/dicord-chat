import discord

from agents.base import InvestigationAgent
from graph.state import AgentState


class InviteInvestigationAgent(InvestigationAgent):
    """招待リンクを調査するエージェント。"""

    @property
    def name(self) -> str:
        return "invite_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        """全招待リンクを収集する。

        Args:
            state: ワークフロー状態。
            guild: 対象サーバー。

        Returns:
            招待リンク情報のリスト。
        """
        invites = await guild.invites()
        if not invites:
            return {"invites": []}

        serialized = []
        for invite in invites:
            channel_name = invite.channel.name if invite.channel else None
            inviter_name = invite.inviter.display_name if invite.inviter else None

            serialized.append({
                "code": invite.code,
                "channel": channel_name,
                "inviter": inviter_name,
                "max_uses": invite.max_uses,
                "uses": invite.uses,
                "max_age": invite.max_age,
                "temporary": invite.temporary,
                "created_at": invite.created_at.isoformat() if invite.created_at else None,
                "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
            })

        return {"invites": serialized}
