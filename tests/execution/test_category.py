"""Tests for CategoryExecutionAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock

import discord
from agents.execution.category import CategoryExecutionAgent
from graph.state import AgentState


@pytest.fixture
def approved_state():
    return {"approved": True, "todos": [], "user_permissions": {}}


@pytest.mark.asyncio
async def test_create_category(mock_guild, approved_state):
    # Arrange
    agent = CategoryExecutionAgent()
    approved_state["todos"] = [{"agent": "category_execution", "action": "create", "params": {"name": "General"}}]
    created_category = MagicMock()
    created_category.name = "General"
    created_category.id = 7001
    mock_guild.create_category_channel = AsyncMock(return_value=created_category)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "General" in result["details"]


@pytest.mark.asyncio
async def test_create_category_missing_name(mock_guild, approved_state):
    # Arrange
    agent = CategoryExecutionAgent()
    approved_state["todos"] = [{"agent": "category_execution", "action": "create", "params": {}}]
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "Missing" in result["details"]


@pytest.mark.asyncio
async def test_edit_category(mock_guild, approved_state, mock_category):
    # Arrange
    agent = CategoryExecutionAgent()
    approved_state["todos"] = [{"agent": "category_execution", "action": "edit", "params": {"category_id": 5001, "name": "New Name"}}]
    mock_category.id = 5001
    mock_category.name = "Old Name"
    mock_category.edit = AsyncMock()
    mock_guild.get_channel = MagicMock(return_value=mock_category)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Edited" in result["details"]


@pytest.mark.asyncio
async def test_edit_category_not_found(mock_guild, approved_state):
    # Arrange
    agent = CategoryExecutionAgent()
    approved_state["todos"] = [{"agent": "category_execution", "action": "edit", "params": {"category_id": 99999}}]
    mock_guild.get_channel = MagicMock(return_value=None)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "not found" in result["details"]


@pytest.mark.asyncio
async def test_delete_category(mock_guild, approved_state, mock_category):
    # Arrange
    agent = CategoryExecutionAgent()
    approved_state["todos"] = [{"agent": "category_execution", "action": "delete", "params": {"category_id": 5001}}]
    mock_category.id = 5001
    mock_category.name = "ToDelete"
    mock_category.delete = AsyncMock()
    mock_guild.get_channel = MagicMock(return_value=mock_category)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Deleted" in result["details"]


@pytest.mark.asyncio
async def test_create_category_with_position(mock_guild, approved_state):
    # Arrange
    agent = CategoryExecutionAgent()
    approved_state["todos"] = [{"agent": "category_execution", "action": "create", "params": {"name": "Important", "position": 1}}]
    created_category = MagicMock()
    created_category.name = "Important"
    created_category.id = 7002
    mock_guild.create_category_channel = AsyncMock(return_value=created_category)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    mock_guild.create_category_channel.assert_called_once()


@pytest.mark.asyncio
async def test_forbidden_error(mock_guild, approved_state):
    # Arrange
    agent = CategoryExecutionAgent()
    approved_state["todos"] = [{"agent": "category_execution", "action": "create", "params": {"name": "Test"}}]
    mock_guild.create_category_channel = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "No permission"))
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False


def test_category_agent_name():
    agent = CategoryExecutionAgent()
    assert agent.name == "category_execution"


def test_action_permissions_defined():
    agent = CategoryExecutionAgent()
    assert "create" in agent.ACTION_PERMISSIONS
    assert "manage_channels" in agent.ACTION_PERMISSIONS["create"]
