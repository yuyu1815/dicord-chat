"""Tests for EmojiExecutionAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock

import discord
from agents.execution.emoji import EmojiExecutionAgent
from graph.state import AgentState


@pytest.fixture
def approved_state():
    return {"approved": True, "todos": [], "user_permissions": {}}


@pytest.mark.asyncio
async def test_create_emoji(mock_guild, approved_state):
    # Arrange
    agent = EmojiExecutionAgent()
    approved_state["todos"] = [{"agent": "emoji_execution", "action": "create", "params": {"name": "happy", "image": b"fake_image_data"}}]
    emoji = MagicMock()
    emoji.name = "happy"
    mock_guild.create_custom_emoji = AsyncMock(return_value=emoji)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Created emoji" in result["details"]


@pytest.mark.asyncio
async def test_edit_emoji(mock_guild, approved_state):
    # Arrange
    agent = EmojiExecutionAgent()
    approved_state["todos"] = [{"agent": "emoji_execution", "action": "edit", "params": {"emoji_id": 1001, "name": "new_name"}}]
    emoji = MagicMock()
    emoji.name = "old_name"
    emoji.edit = AsyncMock()
    mock_guild.get_emoji = MagicMock(return_value=emoji)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Edited emoji" in result["details"]


@pytest.mark.asyncio
async def test_edit_emoji_not_found(mock_guild, approved_state):
    # Arrange
    agent = EmojiExecutionAgent()
    approved_state["todos"] = [{"agent": "emoji_execution", "action": "edit", "params": {"emoji_id": 99999}}]
    mock_guild.get_emoji = MagicMock(return_value=None)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "not found" in result["details"].lower()


@pytest.mark.asyncio
async def test_delete_emoji(mock_guild, approved_state):
    # Arrange
    agent = EmojiExecutionAgent()
    approved_state["todos"] = [{"agent": "emoji_execution", "action": "delete", "params": {"emoji_id": 1001}}]
    emoji = MagicMock()
    emoji.name = "to_delete"
    emoji.delete = AsyncMock()
    mock_guild.get_emoji = MagicMock(return_value=emoji)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Deleted emoji" in result["details"]


@pytest.mark.asyncio
async def test_delete_emoji_not_found(mock_guild, approved_state):
    # Arrange
    agent = EmojiExecutionAgent()
    approved_state["todos"] = [{"agent": "emoji_execution", "action": "delete", "params": {"emoji_id": 99999}}]
    mock_guild.get_emoji = MagicMock(return_value=None)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "not found" in result["details"].lower()


@pytest.mark.asyncio
async def test_create_emoji_with_roles(mock_guild, approved_state, mock_role):
    # Arrange
    agent = EmojiExecutionAgent()
    approved_state["todos"] = [{"agent": "emoji_execution", "action": "create", "params": {"name": "vip_emoji", "image": b"data", "roles": [3001]}}]
    emoji = MagicMock()
    emoji.name = "vip_emoji"
    mock_role.id = 3001
    mock_guild.create_custom_emoji = AsyncMock(return_value=emoji)
    mock_guild.get_role = MagicMock(return_value=mock_role)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True


@pytest.mark.asyncio
async def test_forbidden_error(mock_guild, approved_state):
    # Arrange
    agent = EmojiExecutionAgent()
    approved_state["todos"] = [{"agent": "emoji_execution", "action": "create", "params": {"name": "test", "image": b"data"}}]
    mock_guild.create_custom_emoji = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "No permission"))
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "No permission" in result["details"]


def test_emoji_agent_name():
    agent = EmojiExecutionAgent()
    assert agent.name == "emoji_execution"


def test_action_permissions_defined():
    agent = EmojiExecutionAgent()
    assert "create" in agent.ACTION_PERMISSIONS
    assert "manage_emojis_and_stickers" in agent.ACTION_PERMISSIONS["create"]
