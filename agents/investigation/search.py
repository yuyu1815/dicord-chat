import discord

from agents.base import InvestigationAgent
from graph.state import AgentState
from i18n import t
from services.search import SearchParams, search_messages

MAX_RESULTS = 25


class SearchInvestigationAgent(InvestigationAgent):
    """ギルド内のメッセージを検索するエージェント。"""

    @property
    def name(self) -> str:
        return "search_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        bot = state.get("bot")
        if not bot:
            return {"error": "Bot instance not available in state"}

        request = state.get("request", "")
        if not request:
            return {"error": t("inv.search_no_query", locale=state.get("locale", "en"))}

        # channel_idがstateにある場合はそのチャンネルに絞り込む
        channel_ids = []
        channel_id = state.get("channel_id")
        if channel_id:
            channel_ids = [channel_id]

        params = SearchParams(
            content=request,
            channel_id=channel_ids,
            limit=MAX_RESULTS,
            sort_by="relevance",
            sort_order="desc",
        )

        result = await search_messages(bot, guild, params)

        if not result.messages:
            return {
                "total_results": result.total_results,
                "messages": [],
                "guild_id": guild.id,
                "guild_name": guild.name,
                "query": request,
                "fetched_count": 0,
            }

        return {
            "total_results": result.total_results,
            "messages": result.messages,
            "guild_id": guild.id,
            "guild_name": guild.name,
            "query": request,
            "fetched_count": len(result.messages),
        }
