"""Tests for EventExecutionAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock

import discord
from agents.execution.event import EventExecutionAgent
from graph.state import AgentState


@pytest.fixture
def approved_state():
    return {"approved": True, "todos": [], "user_permissions": {}}


@pytest.mark.asyncio
async def test_create_event(mock_guild, approved_state):
    # Arrange
    agent = EventExecutionAgent()
    approved_state["todos"] = [{"agent": "event_execution", "action": "create", "params": {"name": "Community Event", "start_time": "2024-03-01T12:00:00", "entity_type": "external"}}]
    event = MagicMock()
    event.name = "Community Event"
    mock_guild.create_scheduled_event = AsyncMock(return_value=event)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Created event" in result["details"]


@pytest.mark.asyncio
async def test_create_event_with_description(mock_guild, approved_state):
    # Arrange
    agent = EventExecutionAgent()
    approved_state["todos"] = [{"agent": "event_execution", "action": "create", "params": {"name": "Workshop", "start_time": "2024-04-01T10:00:00", "description": "Learn together", "entity_type": "external"}}]
    event = MagicMock()
    event.name = "Workshop"
    mock_guild.create_scheduled_event = AsyncMock(return_value=event)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True


@pytest.mark.asyncio
async def test_edit_event(mock_guild, approved_state):
    # Arrange
    agent = EventExecutionAgent()
    approved_state["todos"] = [{"agent": "event_execution", "action": "edit", "params": {"event_id": 1001, "name": "Updated Event"}}]
    event = MagicMock()
    event.name = "Old Event"
    event.edit = AsyncMock()
    mock_guild.get_scheduled_event = MagicMock(return_value=event)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Edited event" in result["details"]


@pytest.mark.asyncio
async def test_edit_event_not_found(mock_guild, approved_state):
    # Arrange
    agent = EventExecutionAgent()
    approved_state["todos"] = [{"agent": "event_execution", "action": "edit", "params": {"event_id": 99999}}]
    mock_guild.get_scheduled_event = MagicMock(return_value=None)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "not found" in result["details"].lower()


@pytest.mark.asyncio
async def test_delete_event(mock_guild, approved_state):
    # Arrange
    agent = EventExecutionAgent()
    approved_state["todos"] = [{"agent": "event_execution", "action": "delete", "params": {"event_id": 1001}}]
    event = MagicMock()
    event.name = "ToDelete"
    event.delete = AsyncMock()
    mock_guild.get_scheduled_event = MagicMock(return_value=event)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Deleted event" in result["details"]


@pytest.mark.asyncio
async def test_delete_event_not_found(mock_guild, approved_state):
    # Arrange
    agent = EventExecutionAgent()
    approved_state["todos"] = [{"agent": "event_execution", "action": "delete", "params": {"event_id": 99999}}]
    mock_guild.get_scheduled_event = MagicMock(return_value=None)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "not found" in result["details"].lower()


@pytest.mark.asyncio
async def test_forbidden_error(mock_guild, approved_state):
    # Arrange
    agent = EventExecutionAgent()
    approved_state["todos"] = [{"agent": "event_execution", "action": "create", "params": {"name": "Test", "start_time": "2024-03-01T12:00:00", "entity_type": "external"}}]
    mock_guild.create_scheduled_event = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "No permission"))
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "Missing permissions" in result["details"]


def test_event_agent_name():
    agent = EventExecutionAgent()
    assert agent.name == "event_execution"


def test_action_permissions_defined():
    agent = EventExecutionAgent()
    assert "create" in agent.ACTION_PERMISSIONS
    assert "manage_events" in agent.ACTION_PERMISSIONS["create"]
