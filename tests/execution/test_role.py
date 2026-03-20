"""Tests for RoleExecutionAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock

import discord
from agents.execution.role import RoleExecutionAgent
from graph.state import AgentState


@pytest.fixture
def approved_state():
    return {"approved": True, "todos": [], "user_permissions": {}}


@pytest.mark.asyncio
async def test_create_role(mock_guild, approved_state):
    # Arrange
    agent = RoleExecutionAgent()
    approved_state["todos"] = [{"agent": "role_execution", "action": "create", "params": {"name": "Moderator"}}]
    created_role = MagicMock()
    created_role.name = "Moderator"
    created_role.id = 5001
    mock_guild.create_role = AsyncMock(return_value=created_role)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Moderator" in result["details"]


@pytest.mark.asyncio
async def test_create_role_with_color(mock_guild, approved_state):
    # Arrange
    agent = RoleExecutionAgent()
    approved_state["todos"] = [{"agent": "role_execution", "action": "create", "params": {"name": "VIP", "color": 0xFF0000}}]
    created_role = MagicMock()
    created_role.name = "VIP"
    created_role.id = 5002
    mock_guild.create_role = AsyncMock(return_value=created_role)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    mock_guild.create_role.assert_called_once()


@pytest.mark.asyncio
async def test_create_role_missing_name(mock_guild, approved_state):
    # Arrange
    agent = RoleExecutionAgent()
    approved_state["todos"] = [{"agent": "role_execution", "action": "create", "params": {}}]
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "Missing" in result["details"]


@pytest.mark.asyncio
async def test_edit_role(mock_guild, approved_state, mock_role):
    # Arrange
    agent = RoleExecutionAgent()
    approved_state["todos"] = [{"agent": "role_execution", "action": "edit", "params": {"role_id": 3001, "name": "Admin"}}]
    mock_role.id = 3001
    mock_role.name = "Old Name"
    mock_role.edit = AsyncMock()
    mock_guild.get_role = MagicMock(return_value=mock_role)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Edited" in result["details"]


@pytest.mark.asyncio
async def test_edit_role_not_found(mock_guild, approved_state):
    # Arrange
    agent = RoleExecutionAgent()
    approved_state["todos"] = [{"agent": "role_execution", "action": "edit", "params": {"role_id": 99999}}]
    mock_guild.get_role = MagicMock(return_value=None)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "not found" in result["details"]


@pytest.mark.asyncio
async def test_delete_role(mock_guild, approved_state, mock_role):
    # Arrange
    agent = RoleExecutionAgent()
    approved_state["todos"] = [{"agent": "role_execution", "action": "delete", "params": {"role_id": 3001}}]
    mock_role.id = 3001
    mock_role.name = "ToDelete"
    mock_role.delete = AsyncMock()
    mock_guild.get_role = MagicMock(return_value=mock_role)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Deleted" in result["details"]


@pytest.mark.asyncio
async def test_assign_role(mock_guild, approved_state, mock_member, mock_role):
    # Arrange
    agent = RoleExecutionAgent()
    approved_state["todos"] = [{"agent": "role_execution", "action": "assign", "params": {"member_id": 2001, "role_id": 3001}}]
    mock_member.id = 2001
    mock_member.display_name = "TestUser"
    mock_member.add_roles = AsyncMock()
    mock_role.id = 3001
    mock_role.name = "VIP"
    mock_guild.get_member = MagicMock(return_value=mock_member)
    mock_guild.get_role = MagicMock(return_value=mock_role)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Assigned" in result["details"]


@pytest.mark.asyncio
async def test_revoke_role(mock_guild, approved_state, mock_member, mock_role):
    # Arrange
    agent = RoleExecutionAgent()
    approved_state["todos"] = [{"agent": "role_execution", "action": "revoke", "params": {"member_id": 2001, "role_id": 3001}}]
    mock_member.id = 2001
    mock_member.display_name = "TestUser"
    mock_member.remove_roles = AsyncMock()
    mock_role.id = 3001
    mock_role.name = "VIP"
    mock_guild.get_member = MagicMock(return_value=mock_member)
    mock_guild.get_role = MagicMock(return_value=mock_role)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Revoked" in result["details"]


@pytest.mark.asyncio
async def test_reorder_roles(mock_guild, approved_state):
    # Arrange
    agent = RoleExecutionAgent()
    approved_state["todos"] = [{"agent": "role_execution", "action": "reorder", "params": {"roles": [{"id": 1, "position": 0}]}}]
    mock_guild.edit_role_positions = AsyncMock()
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Reordered" in result["details"]


@pytest.mark.asyncio
async def test_forbidden_error(mock_guild, approved_state):
    # Arrange
    agent = RoleExecutionAgent()
    approved_state["todos"] = [{"agent": "role_execution", "action": "create", "params": {"name": "Test"}}]
    mock_guild.create_role = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "No permission"))
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "No permission" in result["details"]


def test_role_agent_name():
    agent = RoleExecutionAgent()
    assert agent.name == "role_execution"


def test_action_permissions_defined():
    agent = RoleExecutionAgent()
    assert "create" in agent.ACTION_PERMISSIONS
    assert "manage_roles" in agent.ACTION_PERMISSIONS["create"]
