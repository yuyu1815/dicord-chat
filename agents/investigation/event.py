import discord

from agents.base import InvestigationAgent
from graph.state import AgentState


class EventInvestigationAgent(InvestigationAgent):
    """スケジュールイベントを調査するエージェント。"""

    @property
    def name(self) -> str:
        return "event_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        """全スケジュールイベントを収集する。

        Args:
            state: ワークフロー状態。
            guild: 対象サーバー。

        Returns:
            イベント情報のリスト。
        """
        if not guild.scheduled_events:
            return {"events": [], "total_count": 0}

        events = []
        for event in guild.scheduled_events:
            creator_name = None
            if event.creator:
                creator_name = event.creator.display_name

            events.append({
                "id": event.id,
                "name": event.name,
                "description": (event.description[:200] + "...") if event.description and len(event.description) > 200 else event.description,
                "start_time": event.start_time.isoformat() if event.start_time else None,
                "end_time": event.end_time.isoformat() if event.end_time else None,
                "location": str(event.location) if event.location else None,
                "creator": creator_name,
                "status": str(event.status),
                "subscriber_count": event.subscriber_count or 0,
                "image_url": event.cover.url if event.cover else None,
            })

        return {"events": events, "total_count": len(events)}
