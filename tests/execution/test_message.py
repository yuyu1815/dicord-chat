"""Tests for MessageExecutionAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock

import discord
from agents.execution.message import MessageExecutionAgent
from graph.state import AgentState


@pytest.fixture
def approved_state():
    return {"approved": True, "todos": [], "user_permissions": {}}


@pytest.mark.asyncio
async def test_send_message(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "send", "params": {"channel_id": 4001, "content": "Hello!"}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "general"
    mock_text_channel.send = AsyncMock(return_value=MagicMock(id=10001))
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Sent message" in result["details"]


@pytest.mark.asyncio
async def test_send_message_missing_channel(mock_guild, approved_state):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "send", "params": {"content": "Hello!"}}]
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "Missing" in result["details"]


@pytest.mark.asyncio
async def test_delete_message(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "delete", "params": {"message_id": 10001}}]
    message = MagicMock()
    message.id = 10001
    message.delete = AsyncMock()
    mock_text_channel.fetch_message = AsyncMock(return_value=message)
    mock_guild.text_channels = [mock_text_channel]
    mock_guild.threads = []
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Deleted" in result["details"]


@pytest.mark.asyncio
async def test_pin_message(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "pin", "params": {"channel_id": 4001, "message_id": 10001}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "general"
    message = MagicMock()
    message.id = 10001
    message.pin = AsyncMock()
    mock_text_channel.fetch_message = AsyncMock(return_value=message)
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Pinned" in result["details"]


@pytest.mark.asyncio
async def test_unpin_message(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "unpin", "params": {"channel_id": 4001, "message_id": 10001}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "general"
    message = MagicMock()
    message.id = 10001
    message.unpin = AsyncMock()
    mock_text_channel.fetch_message = AsyncMock(return_value=message)
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Unpinned" in result["details"]


@pytest.mark.asyncio
async def test_add_reaction(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "add_reaction", "params": {"channel_id": 4001, "message_id": 10001, "emoji": "👍"}}]
    mock_text_channel.id = 4001
    message = MagicMock()
    message.id = 10001
    message.add_reaction = AsyncMock()
    mock_text_channel.fetch_message = AsyncMock(return_value=message)
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "reaction" in result["details"].lower()


@pytest.mark.asyncio
async def test_clear_reactions(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "clear_reactions", "params": {"channel_id": 4001, "message_id": 10001}}]
    mock_text_channel.id = 4001
    message = MagicMock()
    message.id = 10001
    message.clear_reactions = AsyncMock()
    mock_text_channel.fetch_message = AsyncMock(return_value=message)
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Cleared" in result["details"]


@pytest.mark.asyncio
async def test_edit_message(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "edit", "params": {"message_id": 10001, "content": "Updated!"}}]
    message = MagicMock()
    message.id = 10001
    message.edit = AsyncMock()
    mock_text_channel.fetch_message = AsyncMock(return_value=message)
    mock_guild.text_channels = [mock_text_channel]
    mock_guild.threads = []
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Edited" in result["details"]


@pytest.mark.asyncio
async def test_forbidden_error(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "send", "params": {"channel_id": 4001, "content": "Hello!"}}]
    mock_text_channel.send = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "No permission"))
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "No permission" in result["details"]


def test_message_agent_name():
    agent = MessageExecutionAgent()
    assert agent.name == "message_execution"


def test_action_permissions_defined():
    agent = MessageExecutionAgent()
    assert "send" in agent.ACTION_PERMISSIONS
    assert "delete" in agent.ACTION_PERMISSIONS
    assert "send_messages" in agent.ACTION_PERMISSIONS["send"]
