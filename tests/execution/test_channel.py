"""Tests for ChannelExecutionAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock

import discord
from agents.execution.channel import ChannelExecutionAgent
from graph.state import AgentState


@pytest.fixture
def approved_state():
    return {"approved": True, "todos": [], "user_permissions": {}}


@pytest.mark.asyncio
async def test_create_text_channel(mock_guild, approved_state):
    # Arrange
    agent = ChannelExecutionAgent()
    approved_state["todos"] = [{"agent": "channel_execution", "action": "create", "params": {"name": "general"}}]
    created_channel = MagicMock()
    created_channel.name = "general"
    created_channel.id = 6001
    mock_guild.create_text_channel = AsyncMock(return_value=created_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "general" in result["details"]


@pytest.mark.asyncio
async def test_create_voice_channel(mock_guild, approved_state):
    # Arrange
    agent = ChannelExecutionAgent()
    approved_state["todos"] = [{"agent": "channel_execution", "action": "create", "params": {"name": "voice", "type": "voice"}}]
    created_channel = MagicMock()
    created_channel.name = "voice"
    created_channel.id = 6002
    mock_guild.create_voice_channel = AsyncMock(return_value=created_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True


@pytest.mark.asyncio
async def test_create_channel_missing_name(mock_guild, approved_state):
    # Arrange
    agent = ChannelExecutionAgent()
    approved_state["todos"] = [{"agent": "channel_execution", "action": "create", "params": {}}]
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "Missing" in result["details"]


@pytest.mark.asyncio
async def test_edit_channel(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = ChannelExecutionAgent()
    approved_state["todos"] = [{"agent": "channel_execution", "action": "edit", "params": {"channel_id": 4001, "name": "new-name"}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "old-name"
    mock_text_channel.edit = AsyncMock()
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Edited" in result["details"]


@pytest.mark.asyncio
async def test_edit_channel_not_found(mock_guild, approved_state):
    # Arrange
    agent = ChannelExecutionAgent()
    approved_state["todos"] = [{"agent": "channel_execution", "action": "edit", "params": {"channel_id": 99999}}]
    mock_guild.get_channel = MagicMock(return_value=None)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "not found" in result["details"]


@pytest.mark.asyncio
async def test_delete_channel(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = ChannelExecutionAgent()
    approved_state["todos"] = [{"agent": "channel_execution", "action": "delete", "params": {"channel_id": 4001}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "to-delete"
    mock_text_channel.delete = AsyncMock()
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Deleted" in result["details"]


@pytest.mark.asyncio
async def test_reorder_channels(mock_guild, approved_state):
    # Arrange
    agent = ChannelExecutionAgent()
    approved_state["todos"] = [{"agent": "channel_execution", "action": "reorder", "params": {"channel_positions": [{"id": 1, "position": 0}]}}]
    mock_guild.edit_channel_positions = AsyncMock()
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Reordered" in result["details"]


@pytest.mark.asyncio
async def test_create_channel_with_category(mock_guild, approved_state, mock_category):
    # Arrange
    agent = ChannelExecutionAgent()
    approved_state["todos"] = [{"agent": "channel_execution", "action": "create", "params": {"name": "new-channel", "category_id": 5001}}]
    created_channel = MagicMock()
    created_channel.name = "new-channel"
    created_channel.id = 6003
    mock_category.id = 5001
    mock_guild.get_channel = MagicMock(return_value=mock_category)
    mock_guild.create_text_channel = AsyncMock(return_value=created_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True


@pytest.mark.asyncio
async def test_forbidden_error(mock_guild, approved_state):
    # Arrange
    agent = ChannelExecutionAgent()
    approved_state["todos"] = [{"agent": "channel_execution", "action": "create", "params": {"name": "test"}}]
    mock_guild.create_text_channel = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "No permission"))
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False


def test_channel_agent_name():
    agent = ChannelExecutionAgent()
    assert agent.name == "channel_execution"


def test_action_permissions_defined():
    agent = ChannelExecutionAgent()
    assert "create" in agent.ACTION_PERMISSIONS
    assert "delete" in agent.ACTION_PERMISSIONS
    assert "manage_channels" in agent.ACTION_PERMISSIONS["create"]
