"""Tests for StageExecutionAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock

import discord
from agents.execution.stage import StageExecutionAgent
from graph.state import AgentState


@pytest.fixture
def approved_state():
    return {"approved": True, "todos": [], "user_permissions": {}}


@pytest.mark.asyncio
async def test_create_stage_instance(mock_guild, approved_state):
    # Arrange
    agent = StageExecutionAgent()
    approved_state["todos"] = [{"agent": "stage_execution", "action": "create_stage_instance", "params": {"channel_id": 6001, "topic": "Welcome Event"}}]
    stage_channel = MagicMock(spec=discord.StageChannel)
    stage_channel.id = 6001
    stage_channel.name = "Main Stage"
    stage_channel.create_instance = AsyncMock(return_value=MagicMock())
    mock_guild.get_channel = MagicMock(return_value=stage_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Created stage instance" in result["details"]


@pytest.mark.asyncio
async def test_create_stage_instance_not_stage(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = StageExecutionAgent()
    approved_state["todos"] = [{"agent": "stage_execution", "action": "create_stage_instance", "params": {"channel_id": 4001}}]
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "not a StageChannel" in result["details"]


@pytest.mark.asyncio
async def test_edit_stage_instance(mock_guild, approved_state):
    # Arrange
    agent = StageExecutionAgent()
    approved_state["todos"] = [{"agent": "stage_execution", "action": "edit_stage_instance", "params": {"channel_id": 6001, "topic": "New Topic"}}]
    stage_instance = MagicMock()
    stage_instance.edit = AsyncMock()
    stage_channel = MagicMock(spec=discord.StageChannel)
    stage_channel.id = 6001
    stage_channel.name = "Main Stage"
    stage_channel.instance = stage_instance
    mock_guild.get_channel = MagicMock(return_value=stage_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Updated" in result["details"]


@pytest.mark.asyncio
async def test_delete_stage_instance(mock_guild, approved_state):
    # Arrange
    agent = StageExecutionAgent()
    approved_state["todos"] = [{"agent": "stage_execution", "action": "delete_stage_instance", "params": {"channel_id": 6001}}]
    stage_instance = MagicMock()
    stage_instance.end = AsyncMock()
    stage_channel = MagicMock(spec=discord.StageChannel)
    stage_channel.id = 6001
    stage_channel.name = "Main Stage"
    stage_channel.instance = stage_instance
    mock_guild.get_channel = MagicMock(return_value=stage_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Ended stage instance" in result["details"]


@pytest.mark.asyncio
async def test_edit_channel(mock_guild, approved_state):
    # Arrange
    agent = StageExecutionAgent()
    approved_state["todos"] = [{"agent": "stage_execution", "action": "edit_channel", "params": {"channel_id": 6001, "name": "Community Stage"}}]
    stage_channel = MagicMock(spec=discord.StageChannel)
    stage_channel.id = 6001
    stage_channel.name = "Old Stage"
    stage_channel.edit = AsyncMock()
    mock_guild.get_channel = MagicMock(return_value=stage_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Edited stage channel" in result["details"]


@pytest.mark.asyncio
async def test_forbidden_error(mock_guild, approved_state):
    # Arrange
    agent = StageExecutionAgent()
    approved_state["todos"] = [{"agent": "stage_execution", "action": "create_stage_instance", "params": {"channel_id": 6001, "topic": "Test"}}]
    stage_channel = MagicMock(spec=discord.StageChannel)
    stage_channel.create_instance = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "No permission"))
    mock_guild.get_channel = MagicMock(return_value=stage_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "Missing permissions" in result["details"]


def test_stage_agent_name():
    agent = StageExecutionAgent()
    assert agent.name == "stage_execution"


def test_action_permissions_defined():
    agent = StageExecutionAgent()
    assert "create_stage_instance" in agent.ACTION_PERMISSIONS
    assert "manage_channels" in agent.ACTION_PERMISSIONS["create_stage_instance"]
