"""Tests for PollInvestigationAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock

import discord
from agents.investigation.poll import PollInvestigationAgent


@pytest.mark.asyncio
async def test_poll_list_empty(mock_guild, empty_state):
    # Arrange
    agent = PollInvestigationAgent()

    async def mock_history(limit):
        return
        yield

    channel = MagicMock()
    channel.history = MagicMock(return_value=mock_history(limit=100))
    mock_guild.text_channels = [channel]

    # Act
    result = await agent.investigate(empty_state, mock_guild)

    # Assert
    assert result["polls"] == []
    assert result["total_count"] == 0


@pytest.mark.asyncio
async def test_poll_list_with_active_poll(mock_guild, empty_state):
    # Arrange
    agent = PollInvestigationAgent()

    poll = MagicMock()
    poll.has_ended = False
    poll.total_votes = 42
    poll.expires_at = None
    poll.question = MagicMock()
    poll.question.text = "Best color?"
    answer = MagicMock()
    answer.text = "Red"
    answer.vote_count = 30
    answer2 = MagicMock()
    answer2.text = "Blue"
    answer2.vote_count = 12
    poll.answers = [answer, answer2]

    message = MagicMock()
    message.poll = poll
    message.id = 5001

    async def mock_history(limit):
        yield message

    channel = MagicMock()
    channel.name = "general"
    channel.id = 4001
    channel.history = MagicMock(return_value=mock_history(limit=100))
    mock_guild.text_channels = [channel]

    # Act
    result = await agent.investigate(empty_state, mock_guild)

    # Assert
    assert result["total_count"] == 1
    assert result["polls"][0]["question"] == "Best color?"
    assert result["polls"][0]["total_votes"] == 42


@pytest.mark.asyncio
async def test_poll_skips_ended(mock_guild, empty_state):
    # Arrange
    agent = PollInvestigationAgent()

    poll = MagicMock()
    poll.has_ended = True
    message = MagicMock()
    message.poll = poll
    message.id = 5001

    async def mock_history(limit):
        yield message

    channel = MagicMock()
    channel.history = MagicMock(return_value=mock_history(limit=100))
    mock_guild.text_channels = [channel]

    # Act
    result = await agent.investigate(empty_state, mock_guild)

    # Assert
    assert result["total_count"] == 0


@pytest.mark.asyncio
async def test_poll_skips_forbidden_channels(mock_guild, empty_state):
    # Arrange
    agent = PollInvestigationAgent()

    async def mock_history(limit):
        raise discord.Forbidden(MagicMock(), "No access")
        yield  # make it an async generator

    channel = MagicMock()
    channel.history = MagicMock(return_value=mock_history(limit=100))
    mock_guild.text_channels = [channel]

    # Act
    result = await agent.investigate(empty_state, mock_guild)

    # Assert
    assert result["polls"] == []
    assert result["total_count"] == 0


def test_poll_agent_name():
    agent = PollInvestigationAgent()
    assert agent.name == "poll_investigation"
