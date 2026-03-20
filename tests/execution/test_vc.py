"""Tests for VoiceChannelExecutionAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock

import discord
from agents.execution.vc import VoiceChannelExecutionAgent
from graph.state import AgentState


@pytest.fixture
def approved_state():
    return {"approved": True, "todos": [], "user_permissions": {}}


@pytest.mark.asyncio
async def test_move_user(mock_guild, approved_state, mock_member, mock_voice_channel):
    # Arrange
    agent = VoiceChannelExecutionAgent()
    approved_state["todos"] = [{"agent": "vc_execution", "action": "move_user", "params": {"user_id": 2001, "channel_id": 4002}}]
    mock_member.id = 2001
    mock_member.display_name = "TestUser"
    mock_member.move_to = AsyncMock()
    mock_voice_channel.id = 4002
    mock_voice_channel.name = "Voice Chat"
    mock_guild.get_member = MagicMock(return_value=mock_member)
    mock_guild.get_channel = MagicMock(return_value=mock_voice_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Moved" in result["details"]


@pytest.mark.asyncio
async def test_mute_user(mock_guild, approved_state, mock_member):
    # Arrange
    agent = VoiceChannelExecutionAgent()
    approved_state["todos"] = [{"agent": "vc_execution", "action": "mute", "params": {"user_id": 2001}}]
    mock_member.id = 2001
    mock_member.display_name = "TestUser"
    mock_member.edit = AsyncMock()
    mock_guild.get_member = MagicMock(return_value=mock_member)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "muted" in result["details"].lower()


@pytest.mark.asyncio
async def test_unmute_user(mock_guild, approved_state, mock_member):
    # Arrange
    agent = VoiceChannelExecutionAgent()
    approved_state["todos"] = [{"agent": "vc_execution", "action": "unmute", "params": {"user_id": 2001}}]
    mock_member.id = 2001
    mock_member.display_name = "TestUser"
    mock_member.edit = AsyncMock()
    mock_guild.get_member = MagicMock(return_value=mock_member)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "unmuted" in result["details"].lower()


@pytest.mark.asyncio
async def test_deafen_user(mock_guild, approved_state, mock_member):
    # Arrange
    agent = VoiceChannelExecutionAgent()
    approved_state["todos"] = [{"agent": "vc_execution", "action": "deafen", "params": {"user_id": 2001}}]
    mock_member.id = 2001
    mock_member.display_name = "TestUser"
    mock_member.edit = AsyncMock()
    mock_guild.get_member = MagicMock(return_value=mock_member)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "deafened" in result["details"].lower()


@pytest.mark.asyncio
async def test_undeafen_user(mock_guild, approved_state, mock_member):
    # Arrange
    agent = VoiceChannelExecutionAgent()
    approved_state["todos"] = [{"agent": "vc_execution", "action": "undeafen", "params": {"user_id": 2001}}]
    mock_member.id = 2001
    mock_member.display_name = "TestUser"
    mock_member.edit = AsyncMock()
    mock_guild.get_member = MagicMock(return_value=mock_member)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "undeafened" in result["details"].lower()


@pytest.mark.asyncio
async def test_disconnect_user(mock_guild, approved_state, mock_member):
    # Arrange
    agent = VoiceChannelExecutionAgent()
    approved_state["todos"] = [{"agent": "vc_execution", "action": "disconnect", "params": {"user_id": 2001}}]
    mock_member.id = 2001
    mock_member.display_name = "TestUser"
    mock_member.move_to = AsyncMock()
    mock_guild.get_member = MagicMock(return_value=mock_member)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Disconnected" in result["details"]


@pytest.mark.asyncio
async def test_edit_voice_channel(mock_guild, approved_state, mock_voice_channel):
    # Arrange
    agent = VoiceChannelExecutionAgent()
    approved_state["todos"] = [{"agent": "vc_execution", "action": "edit_channel", "params": {"channel_id": 4002, "name": "New Voice", "bitrate": 128000}}]
    mock_voice_channel.id = 4002
    mock_voice_channel.name = "Old Voice"
    mock_voice_channel.edit = AsyncMock()
    mock_guild.get_channel = MagicMock(return_value=mock_voice_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Edited" in result["details"]


@pytest.mark.asyncio
async def test_member_not_found(mock_guild, approved_state):
    # Arrange
    agent = VoiceChannelExecutionAgent()
    approved_state["todos"] = [{"agent": "vc_execution", "action": "mute", "params": {"user_id": 99999}}]
    mock_guild.get_member = MagicMock(return_value=None)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "not found" in result["details"]


@pytest.mark.asyncio
async def test_forbidden_error(mock_guild, approved_state, mock_member):
    # Arrange
    agent = VoiceChannelExecutionAgent()
    approved_state["todos"] = [{"agent": "vc_execution", "action": "mute", "params": {"user_id": 2001}}]
    mock_member.id = 2001
    mock_member.edit = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "No permission"))
    mock_guild.get_member = MagicMock(return_value=mock_member)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False


def test_vc_agent_name():
    agent = VoiceChannelExecutionAgent()
    assert agent.name == "vc_execution"


def test_action_permissions_defined():
    agent = VoiceChannelExecutionAgent()
    assert "mute" in agent.ACTION_PERMISSIONS
    assert "move_members" in agent.ACTION_PERMISSIONS["move_user"]
