"""Tests for SoundboardExecutionAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock

import discord
from agents.execution.soundboard import SoundboardExecutionAgent
from graph.state import AgentState


@pytest.fixture
def approved_state():
    return {"approved": True, "todos": [], "user_permissions": {}}


@pytest.mark.asyncio
async def test_create_sound(mock_guild, approved_state):
    # Arrange
    agent = SoundboardExecutionAgent()
    approved_state["todos"] = [{"agent": "soundboard_execution", "action": "create", "params": {"name": "applause", "sound": b"audio_data"}}]
    sound = MagicMock()
    sound.name = "applause"
    mock_guild.create_soundboard_sound = AsyncMock(return_value=sound)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Created soundboard sound" in result["details"]


@pytest.mark.asyncio
async def test_create_sound_with_options(mock_guild, approved_state):
    # Arrange
    agent = SoundboardExecutionAgent()
    approved_state["todos"] = [{"agent": "soundboard_execution", "action": "create", "params": {"name": "drumroll", "sound": b"data", "emoji": "🥁", "volume": 0.8}}]
    sound = MagicMock()
    sound.name = "drumroll"
    mock_guild.create_soundboard_sound = AsyncMock(return_value=sound)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True


@pytest.mark.asyncio
async def test_edit_sound(mock_guild, approved_state):
    # Arrange
    agent = SoundboardExecutionAgent()
    approved_state["todos"] = [{"agent": "soundboard_execution", "action": "edit", "params": {"sound_id": 1001, "name": "new_name"}}]
    sound = MagicMock()
    sound.name = "old_name"
    sound.edit = AsyncMock()
    mock_guild.get_soundboard_sound = MagicMock(return_value=sound)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Edited soundboard sound" in result["details"]


@pytest.mark.asyncio
async def test_edit_sound_not_found(mock_guild, approved_state):
    # Arrange
    agent = SoundboardExecutionAgent()
    approved_state["todos"] = [{"agent": "soundboard_execution", "action": "edit", "params": {"sound_id": 99999}}]
    mock_guild.get_soundboard_sound = MagicMock(return_value=None)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "not found" in result["details"].lower()


@pytest.mark.asyncio
async def test_delete_sound(mock_guild, approved_state):
    # Arrange
    agent = SoundboardExecutionAgent()
    approved_state["todos"] = [{"agent": "soundboard_execution", "action": "delete", "params": {"sound_id": 1001}}]
    sound = MagicMock()
    sound.name = "to_delete"
    sound.delete = AsyncMock()
    mock_guild.get_soundboard_sound = MagicMock(return_value=sound)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Deleted soundboard sound" in result["details"]


@pytest.mark.asyncio
async def test_delete_sound_not_found(mock_guild, approved_state):
    # Arrange
    agent = SoundboardExecutionAgent()
    approved_state["todos"] = [{"agent": "soundboard_execution", "action": "delete", "params": {"sound_id": 99999}}]
    mock_guild.get_soundboard_sound = MagicMock(return_value=None)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "not found" in result["details"].lower()


@pytest.mark.asyncio
async def test_forbidden_error(mock_guild, approved_state):
    # Arrange
    agent = SoundboardExecutionAgent()
    approved_state["todos"] = [{"agent": "soundboard_execution", "action": "create", "params": {"name": "test", "sound": b"data"}}]
    mock_guild.create_soundboard_sound = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "No permission"))
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "Missing permissions" in result["details"]


def test_soundboard_agent_name():
    agent = SoundboardExecutionAgent()
    assert agent.name == "soundboard_execution"


def test_action_permissions_defined():
    agent = SoundboardExecutionAgent()
    assert "create" in agent.ACTION_PERMISSIONS
    assert "manage_expressions" in agent.ACTION_PERMISSIONS["create"]
