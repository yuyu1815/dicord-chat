"""Tests for PollExecutionAgent using AAA pattern."""
import datetime

import pytest
from unittest.mock import MagicMock, AsyncMock

import discord
from agents.execution.poll import PollExecutionAgent


@pytest.fixture
def approved_state():
    return {"approved": True, "todos": [], "user_permissions": {}, "bot": None}


@pytest.mark.asyncio
async def test_create_poll(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = PollExecutionAgent()
    approved_state["todos"] = [{"agent": "poll_execution", "action": "create", "params": {"channel_id": 4001, "question": "Best color?", "answers": [{"text": "Red"}, {"text": "Blue"}]}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "general"
    message = MagicMock()
    message.id = 5001
    mock_text_channel.send = AsyncMock(return_value=message)
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    assert "Created poll" in result["details"]
    mock_text_channel.send.assert_called_once()
    call_kwargs = mock_text_channel.send.call_args[1]
    assert "poll" in call_kwargs


@pytest.mark.asyncio
async def test_create_poll_with_multiple(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = PollExecutionAgent()
    approved_state["todos"] = [{"agent": "poll_execution", "action": "create", "params": {"channel_id": 4001, "question": "Pick many?", "answers": [{"text": "A"}, {"text": "B"}], "multiple": True}}]
    mock_text_channel.id = 4001
    message = MagicMock()
    message.id = 5002
    mock_text_channel.send = AsyncMock(return_value=message)
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    call_kwargs = mock_text_channel.send.call_args[1]
    assert call_kwargs["poll"].multiple is True


@pytest.mark.asyncio
async def test_create_poll_with_duration(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = PollExecutionAgent()
    approved_state["todos"] = [{"agent": "poll_execution", "action": "create", "params": {"channel_id": 4001, "question": "Quick poll?", "answers": [{"text": "Yes"}], "duration": 1}}]
    mock_text_channel.id = 4001
    message = MagicMock()
    message.id = 5003
    mock_text_channel.send = AsyncMock(return_value=message)
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    call_kwargs = mock_text_channel.send.call_args[1]
    assert call_kwargs["poll"].duration == datetime.timedelta(hours=1)


@pytest.mark.asyncio
async def test_create_poll_missing_question(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = PollExecutionAgent()
    approved_state["todos"] = [{"agent": "poll_execution", "action": "create", "params": {"channel_id": 4001, "answers": [{"text": "A"}]}}]
    mock_text_channel.id = 4001
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False
    assert "question" in result["details"].lower()


@pytest.mark.asyncio
async def test_create_poll_missing_answers(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = PollExecutionAgent()
    approved_state["todos"] = [{"agent": "poll_execution", "action": "create", "params": {"channel_id": 4001, "question": "Test?"}}]
    mock_text_channel.id = 4001
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False
    assert "answers" in result["details"].lower()


@pytest.mark.asyncio
async def test_create_poll_channel_not_found(mock_guild, approved_state):
    # Arrange
    agent = PollExecutionAgent()
    approved_state["todos"] = [{"agent": "poll_execution", "action": "create", "params": {"channel_id": 99999, "question": "Test?", "answers": [{"text": "A"}]}}]
    mock_guild.get_channel = MagicMock(return_value=None)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False
    assert "not found" in result["details"].lower()


@pytest.mark.asyncio
async def test_end_poll(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = PollExecutionAgent()
    approved_state["todos"] = [{"agent": "poll_execution", "action": "end", "params": {"channel_id": 4001, "message_id": 5001}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "general"
    poll = MagicMock()
    poll.end = AsyncMock()
    message = MagicMock()
    message.id = 5001
    message.poll = poll
    mock_text_channel.fetch_message = AsyncMock(return_value=message)
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    assert "Ended poll" in result["details"]
    poll.end.assert_called_once()


@pytest.mark.asyncio
async def test_end_poll_message_not_found(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = PollExecutionAgent()
    approved_state["todos"] = [{"agent": "poll_execution", "action": "end", "params": {"channel_id": 4001, "message_id": 99999}}]
    mock_text_channel.id = 4001
    mock_text_channel.fetch_message = AsyncMock(side_effect=discord.NotFound(MagicMock(), "Not found"))
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False
    assert "not found" in result["details"].lower()


@pytest.mark.asyncio
async def test_end_poll_not_a_poll(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = PollExecutionAgent()
    approved_state["todos"] = [{"agent": "poll_execution", "action": "end", "params": {"channel_id": 4001, "message_id": 5001}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "general"
    message = MagicMock()
    message.id = 5001
    message.poll = None
    mock_text_channel.fetch_message = AsyncMock(return_value=message)
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False


def test_poll_agent_name():
    agent = PollExecutionAgent()
    assert agent.name == "poll_execution"


def test_action_permissions_defined():
    agent = PollExecutionAgent()
    assert "create" in agent.ACTION_PERMISSIONS
    assert "end" in agent.ACTION_PERMISSIONS
