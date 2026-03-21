"""外部URLをスクレイピングしてMarkdownを取得するエージェント。"""

import re

from agents.base import InvestigationAgent
from graph.state import AgentState
from services.scraper import scrape_url, ScrapeError

_URL_PATTERN = re.compile(r"https?://\S+")


class UrlScraperInvestigationAgent(InvestigationAgent):
    """ユーザーのリクエストに含まれるURLをスクレイピングするエージェント。"""

    @property
    def name(self) -> str:
        return "url_scraper_investigation"

    async def investigate(self, state: AgentState, guild) -> dict:
        request = state.get("request", "")
        if not request:
            return {"error": "No request content"}

        urls = _URL_PATTERN.findall(request)
        if not urls:
            return {"error": "No URLs found in request"}

        results = []
        errors = []

        for url in urls:
            url = url.rstrip(".,;:!?)》]")
            try:
                md = await scrape_url(url)
                results.append({"url": url, "content": md})
            except ScrapeError as e:
                errors.append({"url": url, "reason": e.reason})

        return {
            "results": results,
            "errors": errors,
            "fetched_count": len(results),
            "error_count": len(errors),
        }
