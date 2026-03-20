import discord

from agents.base import InvestigationAgent
from graph.state import AgentState


class WebhookInvestigationAgent(InvestigationAgent):
    """Webhookを調査するエージェント。"""

    @property
    def name(self) -> str:
        return "webhook_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        """全テキストチャンネルのWebhookを収集する。

        Args:
            state: ワークフロー状態。
            guild: 対象サーバー。

        Returns:
            Webhook情報のリスト。
        """
        if not guild.text_channels:
            return {"webhooks": [], "total_count": 0}

        all_webhooks = []
        for channel in guild.text_channels:
            webhooks = await channel.webhooks()
            for wh in webhooks:
                all_webhooks.append({
                    "id": wh.id,
                    "name": wh.name,
                    "channel": wh.channel.name if wh.channel else None,
                    "avatar_url": wh.display_avatar.url if wh.display_avatar else None,
                    "url": wh.url,
                    "guild_id": wh.guild_id,
                })

        return {"webhooks": all_webhooks, "total_count": len(all_webhooks)}
