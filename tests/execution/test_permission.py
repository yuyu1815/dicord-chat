"""Tests for PermissionExecutionAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

import discord
from agents.execution.permission import PermissionExecutionAgent
from graph.state import AgentState


@pytest.fixture
def approved_state():
    return {"approved": True, "todos": [], "user_permissions": {}}


@pytest.mark.asyncio
async def test_set_channel_permission(mock_guild, approved_state, mock_text_channel, mock_role):
    # Arrange
    agent = PermissionExecutionAgent()
    approved_state["todos"] = [{"agent": "permission_execution", "action": "set_channel_permission", "params": {"channel_id": 4001, "target_id": 3001, "target_type": "role", "allow_perms": 2048}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "general"
    mock_text_channel.set_permissions = AsyncMock()
    mock_role.id = 3001
    mock_role.name = "Moderator"
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    mock_guild.get_role = MagicMock(return_value=mock_role)
    
    # Act - Patch PermissionOverwrite to avoid initialization issues
    with patch('discord.PermissionOverwrite'):
        result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Moderator" in result["details"]


@pytest.mark.asyncio
async def test_set_channel_permission_member(mock_guild, approved_state, mock_text_channel, mock_member):
    # Arrange
    agent = PermissionExecutionAgent()
    approved_state["todos"] = [{"agent": "permission_execution", "action": "set_channel_permission", "params": {"channel_id": 4001, "target_id": 2001, "target_type": "member", "allow_perms": 1024}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "general"
    mock_text_channel.set_permissions = AsyncMock()
    mock_member.id = 2001
    mock_member.display_name = "TestUser"
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    mock_guild.get_member = MagicMock(return_value=mock_member)
    
    # Act
    with patch('discord.PermissionOverwrite'):
        result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "TestUser" in result["details"]


@pytest.mark.asyncio
async def test_set_permission_missing_channel(mock_guild, approved_state):
    # Arrange
    agent = PermissionExecutionAgent()
    approved_state["todos"] = [{"agent": "permission_execution", "action": "set_channel_permission", "params": {"target_id": 3001}}]
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "Missing" in result["details"]


@pytest.mark.asyncio
async def test_set_permission_channel_not_found(mock_guild, approved_state):
    # Arrange
    agent = PermissionExecutionAgent()
    approved_state["todos"] = [{"agent": "permission_execution", "action": "set_channel_permission", "params": {"channel_id": 99999, "target_id": 3001}}]
    mock_guild.get_channel = MagicMock(return_value=None)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "not found" in result["details"]


@pytest.mark.asyncio
async def test_delete_channel_permission(mock_guild, approved_state, mock_text_channel, mock_role):
    # Arrange
    agent = PermissionExecutionAgent()
    approved_state["todos"] = [{"agent": "permission_execution", "action": "delete_channel_permission", "params": {"channel_id": 4001, "overwrite_id": 3001}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "general"
    mock_text_channel.set_permissions = AsyncMock()
    mock_role.id = 3001
    mock_role.name = "Muted"
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    mock_guild.get_role = MagicMock(return_value=mock_role)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Cleared" in result["details"]


@pytest.mark.asyncio
async def test_sync_permissions(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = PermissionExecutionAgent()
    approved_state["todos"] = [{"agent": "permission_execution", "action": "sync_permissions", "params": {"channel_id": 4001}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "general"
    mock_text_channel.edit = AsyncMock()
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Synced" in result["details"]


@pytest.mark.asyncio
async def test_sync_permissions_with_category(mock_guild, approved_state, mock_text_channel, mock_category):
    # Arrange
    agent = PermissionExecutionAgent()
    approved_state["todos"] = [{"agent": "permission_execution", "action": "sync_permissions", "params": {"channel_id": 4001, "category_id": 5001}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "general"
    mock_text_channel.edit = AsyncMock()
    mock_category.id = 5001
    mock_guild.get_channel = MagicMock(side_effect=lambda x: mock_text_channel if x == 4001 else mock_category)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True


@pytest.mark.asyncio
async def test_forbidden_error(mock_guild, approved_state, mock_text_channel, mock_role):
    # Arrange
    agent = PermissionExecutionAgent()
    approved_state["todos"] = [{"agent": "permission_execution", "action": "set_channel_permission", "params": {"channel_id": 4001, "target_id": 3001}}]
    mock_text_channel.id = 4001
    mock_text_channel.set_permissions = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "No permission"))
    mock_role.id = 3001
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    mock_guild.get_role = MagicMock(return_value=mock_role)
    
    # Act
    with patch('discord.PermissionOverwrite'):
        result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False


def test_permission_agent_name():
    agent = PermissionExecutionAgent()
    assert agent.name == "permission_execution"


def test_action_permissions_defined():
    agent = PermissionExecutionAgent()
    assert "set_channel_permission" in agent.ACTION_PERMISSIONS
    assert "manage_roles" in agent.ACTION_PERMISSIONS["set_channel_permission"]
