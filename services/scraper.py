"""URL スクレイピングサービス。

Scrapling StealthyFetcher でURLを取得し、html-to-markdown でMarkdownに変換する。
"""

import asyncio
import logging

from html_to_markdown import convert_to_markdown as _html_to_md

logger = logging.getLogger("discord_bot")

# 変換時に除去するノイズタグ
_STRIP_TAGS = ["script", "style", "svg", "nav", "header", "footer"]

# 本文領域を特定するCSSセレクタ（優先順）
_CONTENT_SELECTORS = ["main", "article", '[role="main"]']


class ScrapeError(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


async def scrape_url(url: str) -> str:
    """URLをスクレイピングしてMarkdown文字列を返す。

    Args:
        url: スクレイピング対象のURL（httpsのみ）。

    Returns:
        変換後のMarkdown文字列。

    Raises:
        ScrapeError: URLが無効、取得失敗、変換失敗の場合。
    """
    if not url.startswith("https://"):
        raise ScrapeError(f"Only HTTPS is allowed: {url}")

    try:
        html = await asyncio.to_thread(_fetch_main_html, url)
    except Exception as e:
        logger.warning("Scraping failed for '%s': %s", url, e)
        raise ScrapeError(f"Failed to fetch '{url}': {e}")

    try:
        return _html_to_md(
            html,
            extract_metadata=False,
            strip=_STRIP_TAGS,
            preprocess=True,
            preprocessing_preset="aggressive",
        )
    except Exception as e:
        logger.warning("HTML-to-Markdown conversion failed for '%s': %s", url, e)
        raise ScrapeError(f"Failed to convert '{url}': {e}")


def _fetch_main_html(url: str) -> str:
    """StealthyFetcherでページを取得し、main/article本文のHTMLを返す（同期）。"""
    from scrapling.fetchers import StealthyFetcher

    page = StealthyFetcher.fetch(url, headless=True, network_idle=True)

    if page.status != 200:
        raise ScrapeError(f"HTTP {page.status} from '{url}'")

    for selector in _CONTENT_SELECTORS:
        elements = page.css(selector)
        if elements:
            return elements[0].html_content

    return page.html_content
