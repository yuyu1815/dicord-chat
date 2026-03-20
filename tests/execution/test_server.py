"""Tests for ServerExecutionAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock
import discord

from agents.execution.server import ServerExecutionAgent
from graph.state import AgentState


@pytest.fixture
def approved_state():
    return {"approved": True, "todos": [], "user_permissions": {}}


@pytest.mark.asyncio
async def test_edit_server_name(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_name", "params": {"name": "New Server Name"}}]
    mock_guild.edit = AsyncMock()
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "edit_name" in result["action"]
    mock_guild.edit.assert_called_once_with(name="New Server Name")


@pytest.mark.asyncio
async def test_edit_server_name_missing_param(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_name", "params": {}}]
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "Missing" in result["details"]


@pytest.mark.asyncio
async def test_edit_server_description(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_description", "params": {"description": "A new description"}}]
    mock_guild.edit = AsyncMock()
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    mock_guild.edit.assert_called_once_with(description="A new description")


@pytest.mark.asyncio
async def test_edit_verification_level(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_verification_level", "params": {"level": "high"}}]
    mock_guild.edit = AsyncMock()
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "high" in result["details"]


@pytest.mark.asyncio
async def test_edit_verification_level_invalid(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_verification_level", "params": {"level": "invalid"}}]
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "Invalid level" in result["details"]


@pytest.mark.asyncio
async def test_edit_system_channel(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_system_channel", "params": {"channel_id": 4001}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "system-messages"
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    mock_guild.edit = AsyncMock()
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    mock_guild.edit.assert_called_once()


@pytest.mark.asyncio
async def test_edit_system_channel_not_found(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_system_channel", "params": {"channel_id": 99999}}]
    mock_guild.get_channel = MagicMock(return_value=None)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "not found" in result["details"]


@pytest.mark.asyncio
async def test_edit_rules_channel(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_rules_channel", "params": {"channel_id": 4001}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "rules"
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    mock_guild.edit = AsyncMock()
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True


@pytest.mark.asyncio
async def test_multiple_actions(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [
        {"agent": "server_execution", "action": "edit_name", "params": {"name": "New Name"}},
        {"agent": "server_execution", "action": "edit_description", "params": {"description": "New Desc"}},
    ]
    mock_guild.edit = AsyncMock()
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "edit_name" in result["action"]
    assert "edit_description" in result["action"]


@pytest.mark.asyncio
async def test_no_matching_todos(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "other_agent", "action": "edit_name", "params": {}}]
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "No matching action" in result["details"]


@pytest.mark.asyncio
async def test_forbidden_error(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_name", "params": {"name": "New"}}]
    mock_guild.edit = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "Missing permissions"))
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "Missing permissions" in result["details"]


def test_server_agent_name():
    # Arrange & Act
    agent = ServerExecutionAgent()
    
    # Assert
    assert agent.name == "server_execution"


def test_action_permissions_defined():
    # Arrange & Act
    agent = ServerExecutionAgent()
    
    # Assert
    assert "edit_name" in agent.ACTION_PERMISSIONS
    assert "edit_description" in agent.ACTION_PERMISSIONS
    assert "manage_guild" in agent.ACTION_PERMISSIONS["edit_name"]
