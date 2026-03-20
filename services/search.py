"""Discordメッセージ検索サービス。

GET /guilds/{guild.id}/messages/search エンドポイントのラッパー。
discord.pyにはこのエンドポイントのラッパーが存在しないため、
bot.http を使って直接リクエストを行う。

202 (Not Yet Indexed) レスポンスのリトライやページネーションを処理する。
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import discord
from discord.http import Route

logger = logging.getLogger("discord_bot")

DEFAULT_LIMIT = 25
MAX_OFFSET = 500  # 安全のためAPI上限(9975)より大幅に低く設定
RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 1.5  # seconds
PAGE_COOLDOWN = 1.0  # seconds, ページネーション間のクールダウン


@dataclass
class SearchParams:
    """検索パラメータ。

    Attributes:
        max_pages: 自動ページネーションで取得する最大ページ数。
            0 の場合は全件取得を試みる（MAX_OFFSETまで）。
    """

    content: str = ""
    author_id: list[int | str] = field(default_factory=list)
    channel_id: list[int | str] = field(default_factory=list)
    mentions: list[int | str] = field(default_factory=list)
    has: list[str] = field(default_factory=list)
    sort_by: str = "relevance"  # "relevance" | "timestamp"
    sort_order: str = "desc"  # "asc" | "desc"
    limit: int = DEFAULT_LIMIT
    offset: int = 0
    max_pages: int = 0  # 0 = 全件取得


@dataclass
class SearchResult:
    """検索結果。"""

    messages: list[dict[str, Any]]
    total_results: int
    retried: bool = False


def _build_params(params: SearchParams) -> dict[str, Any]:
    """SearchParamsをAPIクエリパラメータに変換する。"""
    query: dict[str, Any] = {"limit": params.limit}

    if params.content:
        query["content"] = params.content[:1024]
    if params.author_id:
        query["author_id"] = [str(a) for a in params.author_id[:100]]
    if params.channel_id:
        query["channel_id"] = [str(c) for c in params.channel_id[:500]]
    if params.mentions:
        query["mentions"] = [str(m) for m in params.mentions[:100]]
    if params.has:
        query["has"] = params.has
    if params.sort_by:
        query["sort_by"] = params.sort_by
    if params.sort_order:
        query["sort_order"] = params.sort_order
    if params.offset:
        query["offset"] = params.offset

    return query


def _normalize_messages(raw: list[list[dict]]) -> list[dict[str, Any]]:
    """ネストされたメッセージ配列をフラットな辞書リストに正規化する。"""
    messages: list[dict[str, Any]] = []
    for group in raw:
        for msg in group:
            messages.append({
                "id": msg.get("id"),
                "author": msg.get("author", {}).get("username", "unknown"),
                "author_id": msg.get("author", {}).get("id"),
                "content": msg.get("content", ""),
                "channel_id": msg.get("channel_id"),
                "timestamp": msg.get("timestamp"),
                "edited_timestamp": msg.get("edited_timestamp"),
                "pinned": msg.get("pinned", False),
                "type": msg.get("type"),
                "mentions": len(msg.get("mentions", [])),
                "attachment_count": len(msg.get("attachments", [])),
                "embed_count": len(msg.get("embeds", [])),
            })
    return messages


async def _fetch_page(
    bot: discord.Client,
    route: Route,
    query: dict[str, Any],
) -> tuple[list[dict[str, Any]], int, float, bool]:
    """単一ページを取得し、正規化済みメッセージ・total・retry_after・リトライ要否を返す。

    Returns:
        (messages, total_results, retry_after, was_retried)
    """
    for attempt in range(RETRY_ATTEMPTS):
        try:
            data = await bot.http.request(route, params=query)

            if not isinstance(data, dict):
                return [], 0, 0.0, False

            total = data.get("total_results", 0)
            retry_after = data.get("retry_after", 0.0)

            if data.get("code") == 202 or (total == 0 and not data.get("messages")):
                wait = retry_after or RETRY_BASE_DELAY * (attempt + 1)
                if attempt < RETRY_ATTEMPTS - 1:
                    logger.debug(
                        "Search returned 202/not indexed, retrying in %.1fs (attempt %d/%d)",
                        wait, attempt + 1, RETRY_ATTEMPTS,
                    )
                    await asyncio.sleep(wait)
                    continue
                return [], total, retry_after, False

            raw_messages = data.get("messages", [])
            messages = _normalize_messages(raw_messages) if raw_messages else []
            return messages, total, retry_after, attempt > 0

        except discord.HTTPException as e:
            logger.warning("Search API error: %s", e)
            return [], 0, 0.0, False
        except Exception as e:
            logger.error("Unexpected search error: %s", e)
            return [], 0, 0.0, False

    return [], 0, 0.0, False


async def search_messages(
    bot: discord.Client,
    guild: discord.Guild,
    params: SearchParams,
) -> SearchResult:
    """ギルド内のメッセージを検索する。

    1回のリクエストで最大25件まで取得可能。
    max_pages=0 の場合は MAX_OFFSET に達するまで全ページを自動取得する。

    Args:
        bot: discord.pyのBotインスタンス。
        guild: 検索対象ギルド。
        params: 検索パラメータ。

    Returns:
        検索結果。
    """
    route = Route(
        "GET",
        "/guilds/{guild_id}/messages/search",
        guild_id=guild.id,
    )

    all_messages: list[dict[str, Any]] = []
    total_results = 0
    retried = False
    offset = params.offset
    page = 0
    max_pages = params.max_pages if params.max_pages > 0 else (MAX_OFFSET // DEFAULT_LIMIT + 1)

    while page < max_pages:
        page += 1
        page_params = SearchParams(
            content=params.content,
            author_id=params.author_id,
            channel_id=params.channel_id,
            mentions=params.mentions,
            has=params.has,
            sort_by=params.sort_by,
            sort_order=params.sort_order,
            limit=params.limit,
            offset=offset,
        )
        query = _build_params(page_params)

        messages, total, retry_after, was_retried = await _fetch_page(bot, route, query)
        if was_retried:
            retried = True
        if not messages and total == 0:
            break

        total_results = total
        all_messages.extend(messages)

        if len(messages) < params.limit:
            break  # 最後のページ

        # APIから retry_after が返された場合はそれに従う
        if retry_after and retry_after > 0:
            logger.debug("Search cooldown: waiting %.1fs before next page", retry_after)
            await asyncio.sleep(retry_after)
        else:
            await asyncio.sleep(PAGE_COOLDOWN)

        offset += params.limit

    return SearchResult(
        messages=all_messages,
        total_results=total_results,
        retried=retried,
    )
