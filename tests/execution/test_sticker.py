"""Tests for StickerExecutionAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock

import discord
from agents.execution.sticker import StickerExecutionAgent
from graph.state import AgentState


@pytest.fixture
def approved_state():
    return {"approved": True, "todos": [], "user_permissions": {}}


@pytest.mark.asyncio
async def test_create_sticker(mock_guild, approved_state):
    # Arrange
    agent = StickerExecutionAgent()
    approved_state["todos"] = [{"agent": "sticker_execution", "action": "create", "params": {"name": "hello", "file": b"sticker_data", "format_type": "png"}}]
    sticker = MagicMock()
    sticker.name = "hello"
    mock_guild.create_sticker = AsyncMock(return_value=sticker)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Created sticker" in result["details"]


@pytest.mark.asyncio
async def test_create_sticker_with_tags(mock_guild, approved_state):
    # Arrange
    agent = StickerExecutionAgent()
    approved_state["todos"] = [{"agent": "sticker_execution", "action": "create", "params": {"name": "wave", "file": b"data", "format_type": "apng", "tags": "wave, hello", "description": "A wave"}}]
    sticker = MagicMock()
    sticker.name = "wave"
    mock_guild.create_sticker = AsyncMock(return_value=sticker)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True


@pytest.mark.asyncio
async def test_edit_sticker(mock_guild, approved_state):
    # Arrange
    agent = StickerExecutionAgent()
    approved_state["todos"] = [{"agent": "sticker_execution", "action": "edit", "params": {"sticker_id": 1001, "name": "new_name"}}]
    sticker = MagicMock()
    sticker.name = "old_name"
    sticker.edit = AsyncMock()
    mock_guild.get_sticker = MagicMock(return_value=sticker)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Edited sticker" in result["details"]


@pytest.mark.asyncio
async def test_edit_sticker_not_found(mock_guild, approved_state):
    # Arrange
    agent = StickerExecutionAgent()
    approved_state["todos"] = [{"agent": "sticker_execution", "action": "edit", "params": {"sticker_id": 99999}}]
    mock_guild.get_sticker = MagicMock(return_value=None)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "not found" in result["details"].lower()


@pytest.mark.asyncio
async def test_delete_sticker(mock_guild, approved_state):
    # Arrange
    agent = StickerExecutionAgent()
    approved_state["todos"] = [{"agent": "sticker_execution", "action": "delete", "params": {"sticker_id": 1001}}]
    sticker = MagicMock()
    sticker.name = "to_delete"
    sticker.delete = AsyncMock()
    mock_guild.get_sticker = MagicMock(return_value=sticker)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Deleted sticker" in result["details"]


@pytest.mark.asyncio
async def test_delete_sticker_not_found(mock_guild, approved_state):
    # Arrange
    agent = StickerExecutionAgent()
    approved_state["todos"] = [{"agent": "sticker_execution", "action": "delete", "params": {"sticker_id": 99999}}]
    mock_guild.get_sticker = MagicMock(return_value=None)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "not found" in result["details"].lower()


@pytest.mark.asyncio
async def test_forbidden_error(mock_guild, approved_state):
    # Arrange
    agent = StickerExecutionAgent()
    approved_state["todos"] = [{"agent": "sticker_execution", "action": "create", "params": {"name": "test", "file": b"data"}}]
    mock_guild.create_sticker = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "No permission"))
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "Missing permissions" in result["details"]


def test_sticker_agent_name():
    agent = StickerExecutionAgent()
    assert agent.name == "sticker_execution"


def test_action_permissions_defined():
    agent = StickerExecutionAgent()
    assert "create" in agent.ACTION_PERMISSIONS
    assert "manage_emojis_and_stickers" in agent.ACTION_PERMISSIONS["create"]
