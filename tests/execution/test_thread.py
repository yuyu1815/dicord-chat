"""Tests for ThreadExecutionAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock

import discord
from agents.execution.thread import ThreadExecutionAgent
from graph.state import AgentState


@pytest.fixture
def approved_state():
    return {"approved": True, "todos": [], "user_permissions": {}}


@pytest.mark.asyncio
async def test_create_thread(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = ThreadExecutionAgent()
    approved_state["todos"] = [{"agent": "thread_execution", "action": "create", "params": {"channel_id": 4001, "name": "Discussion"}}]
    created_thread = MagicMock()
    created_thread.name = "Discussion"
    created_thread.id = 8001
    mock_text_channel.id = 4001
    mock_text_channel.create_thread = AsyncMock(return_value=created_thread)
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Discussion" in result["details"]


@pytest.mark.asyncio
async def test_create_private_thread(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = ThreadExecutionAgent()
    approved_state["todos"] = [{"agent": "thread_execution", "action": "create", "params": {"channel_id": 4001, "name": "Private", "type": "private"}}]
    created_thread = MagicMock()
    created_thread.name = "Private"
    created_thread.id = 8002
    mock_text_channel.id = 4001
    mock_text_channel.create_thread = AsyncMock(return_value=created_thread)
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True


@pytest.mark.asyncio
async def test_create_thread_missing_channel(mock_guild, approved_state):
    # Arrange
    agent = ThreadExecutionAgent()
    approved_state["todos"] = [{"agent": "thread_execution", "action": "create", "params": {"name": "Test"}}]
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "Missing" in result["details"]


@pytest.mark.asyncio
async def test_edit_thread(mock_guild, approved_state):
    # Arrange
    agent = ThreadExecutionAgent()
    approved_state["todos"] = [{"agent": "thread_execution", "action": "edit", "params": {"thread_id": 8001, "name": "Updated"}}]
    thread = MagicMock()
    thread.id = 8001
    thread.name = "Old Name"
    thread.edit = AsyncMock()
    mock_guild.get_thread = MagicMock(return_value=thread)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Edited" in result["details"]


@pytest.mark.asyncio
async def test_archive_thread(mock_guild, approved_state):
    # Arrange
    agent = ThreadExecutionAgent()
    approved_state["todos"] = [{"agent": "thread_execution", "action": "edit", "params": {"thread_id": 8001, "archived": True}}]
    thread = MagicMock()
    thread.id = 8001
    thread.name = "Old Thread"
    thread.edit = AsyncMock()
    mock_guild.get_thread = MagicMock(return_value=thread)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True


@pytest.mark.asyncio
async def test_delete_thread(mock_guild, approved_state):
    # Arrange
    agent = ThreadExecutionAgent()
    approved_state["todos"] = [{"agent": "thread_execution", "action": "delete", "params": {"thread_id": 8001}}]
    thread = MagicMock()
    thread.id = 8001
    thread.name = "ToDelete"
    thread.delete = AsyncMock()
    mock_guild.get_thread = MagicMock(return_value=thread)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Deleted" in result["details"]


@pytest.mark.asyncio
async def test_add_member_to_thread(mock_guild, approved_state, mock_member):
    # Arrange
    agent = ThreadExecutionAgent()
    approved_state["todos"] = [{"agent": "thread_execution", "action": "add_member", "params": {"thread_id": 8001, "member_id": 2001}}]
    thread = MagicMock()
    thread.id = 8001
    thread.name = "TestThread"
    thread.add_member = AsyncMock()
    mock_member.id = 2001
    mock_member.display_name = "TestUser"
    mock_guild.get_thread = MagicMock(return_value=thread)
    mock_guild.get_member = MagicMock(return_value=mock_member)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Added" in result["details"]


@pytest.mark.asyncio
async def test_join_thread(mock_guild, approved_state):
    # Arrange
    agent = ThreadExecutionAgent()
    approved_state["todos"] = [{"agent": "thread_execution", "action": "join", "params": {"thread_id": 8001}}]
    thread = MagicMock()
    thread.id = 8001
    thread.name = "TestThread"
    thread.join = AsyncMock()
    mock_guild.get_thread = MagicMock(return_value=thread)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Joined" in result["details"]


@pytest.mark.asyncio
async def test_leave_thread(mock_guild, approved_state):
    # Arrange
    agent = ThreadExecutionAgent()
    approved_state["todos"] = [{"agent": "thread_execution", "action": "leave", "params": {"thread_id": 8001}}]
    thread = MagicMock()
    thread.id = 8001
    thread.name = "TestThread"
    thread.leave = AsyncMock()
    mock_guild.get_thread = MagicMock(return_value=thread)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Left" in result["details"]


@pytest.mark.asyncio
async def test_thread_not_found(mock_guild, approved_state):
    # Arrange
    agent = ThreadExecutionAgent()
    approved_state["todos"] = [{"agent": "thread_execution", "action": "edit", "params": {"thread_id": 99999}}]
    mock_guild.get_thread = MagicMock(return_value=None)
    mock_guild.text_channels = []
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "not found" in result["details"]


def test_thread_agent_name():
    agent = ThreadExecutionAgent()
    assert agent.name == "thread_execution"


def test_action_permissions_defined():
    agent = ThreadExecutionAgent()
    assert "create" in agent.ACTION_PERMISSIONS
    assert "manage_threads" in agent.ACTION_PERMISSIONS["edit"]
