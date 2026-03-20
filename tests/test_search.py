"""Tests for services/search.py"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.search import (
    SearchParams,
    SearchResult,
    _build_params,
    _normalize_messages,
    search_messages,
)


class TestBuildParams:
    def test_content_only(self):
        params = SearchParams(content="hello world")
        result = _build_params(params)
        assert result["content"] == "hello world"
        assert result["limit"] == 25

    def test_all_params(self):
        params = SearchParams(
            content="test",
            author_id=[123, 456],
            channel_id=[789],
            mentions=[111],
            has=["link", "file"],
            sort_by="timestamp",
            sort_order="asc",
            limit=10,
            offset=50,
        )
        result = _build_params(params)
        assert result["content"] == "test"
        assert result["author_id"] == ["123", "456"]
        assert result["channel_id"] == ["789"]
        assert result["mentions"] == ["111"]
        assert result["has"] == ["link", "file"]
        assert result["sort_by"] == "timestamp"
        assert result["sort_order"] == "asc"
        assert result["limit"] == 10
        assert result["offset"] == 50

    def test_content_truncated_to_1024(self):
        params = SearchParams(content="x" * 2000)
        result = _build_params(params)
        assert len(result["content"]) == 1024

    def test_empty_params(self):
        params = SearchParams()
        result = _build_params(params)
        assert result == {"limit": 25, "sort_by": "relevance", "sort_order": "desc"}


class TestNormalizeMessages:
    def test_nested_to_flat(self):
        raw = [
            [{"id": "1", "author": {"username": "a", "id": "10"}, "content": "hello", "channel_id": "100", "timestamp": "2025-01-01T00:00:00"}],
            [{"id": "2", "author": {"username": "b", "id": "20"}, "content": "world", "channel_id": "200", "timestamp": "2025-01-02T00:00:00"}],
        ]
        result = _normalize_messages(raw)
        assert len(result) == 2
        assert result[0]["author"] == "a"
        assert result[1]["content"] == "world"

    def test_empty_input(self):
        assert _normalize_messages([]) == []

    def test_counts_attachments_and_embeds(self):
        raw = [[{
            "id": "1",
            "author": {"username": "u", "id": "1"},
            "content": "c",
            "channel_id": "1",
            "timestamp": "t",
            "attachments": [{"id": "a1"}, {"id": "a2"}],
            "embeds": [{"type": "rich"}],
            "mentions": [{"id": "m1"}, {"id": "m2"}, {"id": "m3"}],
        }]]
        result = _normalize_messages(raw)
        assert result[0]["attachment_count"] == 2
        assert result[0]["embed_count"] == 1
        assert result[0]["mentions"] == 3


class TestSearchMessages:
    @pytest.mark.asyncio
    async def test_successful_search(self):
        bot = MagicMock()
        bot.http.request = AsyncMock(return_value={
            "total_results": 2,
            "messages": [
                [{"id": "1", "author": {"username": "a", "id": "1"}, "content": "hi", "channel_id": "c", "timestamp": "t"}],
            ],
        })
        guild = MagicMock()
        guild.id = 123

        params = SearchParams(content="hi")
        result = await search_messages(bot, guild, params)

        assert result.total_results == 2
        assert len(result.messages) == 1
        assert result.messages[0]["content"] == "hi"

    @pytest.mark.asyncio
    async def test_no_results(self):
        bot = MagicMock()
        bot.http.request = AsyncMock(return_value={
            "total_results": 0,
            "messages": [],
        })
        guild = MagicMock()
        guild.id = 123

        params = SearchParams(content="nothing")
        result = await search_messages(bot, guild, params)

        assert result.total_results == 0
        assert result.messages == []

    @pytest.mark.asyncio
    async def test_http_exception(self):
        import discord
        bot = MagicMock()
        bot.http.request = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "fail"))
        guild = MagicMock()
        guild.id = 123

        params = SearchParams(content="test")
        result = await search_messages(bot, guild, params)

        assert result.messages == []
        assert result.total_results == 0

    @pytest.mark.asyncio
    async def test_non_dict_response(self):
        bot = MagicMock()
        bot.http.request = AsyncMock(return_value="not a dict")
        guild = MagicMock()
        guild.id = 123

        params = SearchParams(content="test")
        result = await search_messages(bot, guild, params)

        assert result.messages == []

    @pytest.mark.asyncio
    async def test_pagination_multiple_pages(self):
        """2ページにまたがる結果が全取得されること。"""
        bot = MagicMock()
        call_count = 0

        async def fake_request(route, params=None):
            nonlocal call_count
            call_count += 1
            offset = (params or {}).get("offset", 0)
            if offset == 0:
                # 1ページ目: 25件、全50件中
                return {
                    "total_results": 50,
                    "messages": [
                        [{"id": str(i), "author": {"username": "u", "id": "1"}, "content": f"msg{i}", "channel_id": "c", "timestamp": "t"}]
                        for i in range(25)
                    ],
                }
            elif offset == 25:
                # 2ページ目: 25件（最後）
                return {
                    "total_results": 50,
                    "messages": [
                        [{"id": str(i), "author": {"username": "u", "id": "1"}, "content": f"msg{i}", "channel_id": "c", "timestamp": "t"}]
                        for i in range(25, 50)
                    ],
                }
            else:
                # 3ページ目以降は返さない
                return {"total_results": 50, "messages": []}

        bot.http.request = fake_request
        guild = MagicMock()
        guild.id = 123

        params = SearchParams(content="test")
        result = await search_messages(bot, guild, params)

        assert call_count == 3  # 2ページ目は25件（limit==25）で止まらず、3ページ目は空で停止
        assert result.total_results == 50
        assert len(result.messages) == 50

    @pytest.mark.asyncio
    async def test_pagination_stops_on_partial_page(self):
        """最後のページがlimit未満の場合にループが停止すること。"""
        bot = MagicMock()
        call_count = 0

        async def fake_request(route, params=None):
            nonlocal call_count
            call_count += 1
            offset = (params or {}).get("offset", 0)
            if offset == 0:
                return {
                    "total_results": 30,
                    "messages": [
                        [{"id": str(i), "author": {"username": "u", "id": "1"}, "content": f"msg{i}", "channel_id": "c", "timestamp": "t"}]
                        for i in range(25)
                    ],
                }
            else:
                # 残り5件
                return {
                    "total_results": 30,
                    "messages": [
                        [{"id": str(i), "author": {"username": "u", "id": "1"}, "content": f"msg{i}", "channel_id": "c", "timestamp": "t"}]
                        for i in range(25, 30)
                    ],
                }

        bot.http.request = fake_request
        guild = MagicMock()
        guild.id = 123

        params = SearchParams(content="test")
        result = await search_messages(bot, guild, params)

        assert call_count == 2
        assert len(result.messages) == 30

    @pytest.mark.asyncio
    async def test_pagination_respects_max_pages(self):
        """max_pagesで取得ページ数が制限されること。"""
        bot = MagicMock()
        bot.http.request = AsyncMock(return_value={
            "total_results": 100,
            "messages": [
                [{"id": str(i), "author": {"username": "u", "id": "1"}, "content": f"msg{i}", "channel_id": "c", "timestamp": "t"}]
                for i in range(25)
            ],
        })
        guild = MagicMock()
        guild.id = 123

        params = SearchParams(content="test", max_pages=2)
        result = await search_messages(bot, guild, params)

        assert bot.http.request.call_count == 2
        assert len(result.messages) == 50
