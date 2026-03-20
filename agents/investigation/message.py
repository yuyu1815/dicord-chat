import discord

from agents.base import InvestigationAgent
from graph.state import AgentState
from i18n import t

MAX_CONTENT_LENGTH = 200
DEFAULT_FETCH_LIMIT = 20


class MessageInvestigationAgent(InvestigationAgent):
    """メッセージ情報を調査するエージェント。"""

    @property
    def name(self) -> str:
        return "message_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        """指定チャンネルの直近メッセージを収集する。

        Args:
            state: ワークフロー状態（``channel_id`` が必要）。
            guild: 対象サーバー。

        Returns:
            メッセージ情報のリストと取得件数。
        """
        channel_id = state.get("channel_id")
        if channel_id is None:
            return {"error": t("inv.channel_required", locale=state.get("locale", "en"))}

        channel = guild.get_channel(channel_id)
        if channel is None:
            return {"error": t("inv.channel_not_found", locale=state.get("locale", "en"), id=channel_id)}

        if not isinstance(channel, discord.abc.Messageable):
            return {"error": t("inv.channel_not_messageable", locale=state.get("locale", "en"), id=channel_id)}

        messages = []
        async for msg in channel.history(limit=DEFAULT_FETCH_LIMIT):
            content = msg.content
            truncated = content[:MAX_CONTENT_LENGTH] if content and len(content) > MAX_CONTENT_LENGTH else content

            messages.append({
                "id": msg.id,
                "author": str(msg.author),
                "content": truncated,
                "created_at": msg.created_at.isoformat(),
                "attachment_count": len(msg.attachments),
                "pinned": msg.pinned,
            })

        return {
            "channel_id": channel_id,
            "channel_name": channel.name if hasattr(channel, "name") else str(channel),
            "messages": messages,
            "fetched_count": len(messages),
        }
