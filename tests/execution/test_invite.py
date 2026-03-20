"""Tests for InviteExecutionAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock

import discord
from agents.execution.invite import InviteExecutionAgent
from graph.state import AgentState


@pytest.fixture
def approved_state():
    return {"approved": True, "todos": [], "user_permissions": {}, "bot": None}


@pytest.mark.asyncio
async def test_create_invite(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = InviteExecutionAgent()
    approved_state["todos"] = [{"agent": "invite_execution", "action": "create", "params": {"channel_id": 4001, "max_uses": 10}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "general"
    invite = MagicMock()
    invite.url = "https://discord.gg/abc123"
    mock_text_channel.create_invite = AsyncMock(return_value=invite)
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    mock_guild.text_channels = [mock_text_channel]
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "abc123" in result["details"]


@pytest.mark.asyncio
async def test_create_invite_with_options(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = InviteExecutionAgent()
    approved_state["todos"] = [{"agent": "invite_execution", "action": "create", "params": {"channel_id": 4001, "max_uses": 5, "max_age": 3600, "temporary": True}}]
    mock_text_channel.id = 4001
    invite = MagicMock()
    invite.url = "https://discord.gg/test"
    mock_text_channel.create_invite = AsyncMock(return_value=invite)
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    mock_guild.text_channels = [mock_text_channel]
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    mock_text_channel.create_invite.assert_called_once()


@pytest.mark.asyncio
async def test_create_invite_channel_not_found(mock_guild, approved_state):
    # Arrange
    agent = InviteExecutionAgent()
    approved_state["todos"] = [{"agent": "invite_execution", "action": "create", "params": {"channel_id": 99999}}]
    mock_guild.get_channel = MagicMock(return_value=None)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False
    assert "not found" in result["details"].lower()


@pytest.mark.asyncio
async def test_delete_invite(mock_guild, approved_state):
    # Arrange
    agent = InviteExecutionAgent()
    approved_state["todos"] = [{"agent": "invite_execution", "action": "delete", "params": {"invite_code": "abc123"}}]
    invite = MagicMock()
    invite.delete = AsyncMock()
    mock_bot = MagicMock()
    mock_bot.fetch_invite = AsyncMock(return_value=invite)
    approved_state["bot"] = mock_bot

    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "abc123" in result["details"]


@pytest.mark.asyncio
async def test_forbidden_error(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = InviteExecutionAgent()
    approved_state["todos"] = [{"agent": "invite_execution", "action": "create", "params": {"channel_id": 4001}}]
    mock_text_channel.create_invite = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "No permission"))
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    mock_guild.text_channels = [mock_text_channel]
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "Missing permissions" in result["details"]


def test_invite_agent_name():
    agent = InviteExecutionAgent()
    assert agent.name == "invite_execution"


def test_action_permissions_defined():
    agent = InviteExecutionAgent()
    assert "create" in agent.ACTION_PERMISSIONS
    assert "delete" in agent.ACTION_PERMISSIONS
