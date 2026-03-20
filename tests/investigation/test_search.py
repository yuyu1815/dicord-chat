"""Tests for agents/investigation/search.py"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.investigation.search import SearchInvestigationAgent
from services.search import SearchResult


@pytest.fixture
def agent():
    return SearchInvestigationAgent()


@pytest.mark.asyncio
async def test_search_investigation(agent):
    bot = MagicMock()
    guild = MagicMock()
    guild.id = 123
    guild.name = "Test Guild"

    fake_messages = [
        {
            "id": "1",
            "author": "alice",
            "content": "hello world",
            "channel_id": "100",
            "timestamp": "2025-01-01T00:00:00",
        },
    ]

    with patch("agents.investigation.search.search_messages", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = SearchResult(messages=fake_messages, total_results=1)
        state = {"request": "hello", "bot": bot}
        result = await agent.investigate(state, guild)

    assert result["total_results"] == 1
    assert len(result["messages"]) == 1
    assert result["messages"][0]["content"] == "hello world"
    assert result["guild_id"] == 123
    assert result["query"] == "hello"

    mock_search.assert_called_once()
    call_params = mock_search.call_args[0][2]
    assert call_params.content == "hello"


@pytest.mark.asyncio
async def test_search_with_channel_id(agent):
    bot = MagicMock()
    guild = MagicMock()

    with patch("agents.investigation.search.search_messages", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = SearchResult(messages=[], total_results=0)
        state = {"request": "test", "bot": bot, "channel_id": 999}
        result = await agent.investigate(state, guild)

    call_params = mock_search.call_args[0][2]
    assert call_params.channel_id == [999]


@pytest.mark.asyncio
async def test_search_no_bot(agent):
    guild = MagicMock()
    state = {"request": "test"}
    result = await agent.investigate(state, guild)
    assert "error" in result


@pytest.mark.asyncio
async def test_search_no_query(agent):
    bot = MagicMock()
    guild = MagicMock()
    state = {"request": "", "bot": bot}
    result = await agent.investigate(state, guild)
    assert "error" in result
