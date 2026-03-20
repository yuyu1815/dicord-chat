"""Tests for AutoModExecutionAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock

import discord
from agents.execution.automod import AutoModExecutionAgent
from graph.state import AgentState


@pytest.fixture
def approved_state():
    return {"approved": True, "todos": [], "user_permissions": {}}


@pytest.mark.asyncio
async def test_create_rule(mock_guild, approved_state):
    # Arrange
    agent = AutoModExecutionAgent()
    approved_state["todos"] = [{"agent": "automod_execution", "action": "create_rule", "params": {"name": "Anti-Spam", "trigger_type": "keyword", "trigger_metadata": {"keyword_filter": ["spam", "scam"]}, "actions": [{"type": "block_message"}]}}]
    rule = MagicMock()
    rule.name = "Anti-Spam"
    mock_guild.create_automod_rule = AsyncMock(return_value=rule)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Created AutoMod rule" in result["details"]


@pytest.mark.asyncio
async def test_create_rule_with_timeout_action(mock_guild, approved_state):
    # Arrange
    agent = AutoModExecutionAgent()
    approved_state["todos"] = [{"agent": "automod_execution", "action": "create_rule", "params": {"name": "Timeout Rule", "trigger_type": "spam", "actions": [{"type": "timeout", "duration": 60}]}}]
    rule = MagicMock()
    rule.name = "Timeout Rule"
    mock_guild.create_automod_rule = AsyncMock(return_value=rule)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True


@pytest.mark.asyncio
async def test_edit_rule(mock_guild, approved_state):
    # Arrange
    agent = AutoModExecutionAgent()
    approved_state["todos"] = [{"agent": "automod_execution", "action": "edit_rule", "params": {"rule_id": 1001, "name": "Updated Rule", "enabled": True}}]
    rule = MagicMock()
    rule.name = "Updated Rule"
    rule.edit = AsyncMock()
    mock_guild.fetch_automod_rule = AsyncMock(return_value=rule)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    assert "Edited AutoMod rule" in result["details"]
    rule.edit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_rule(mock_guild, approved_state):
    # Arrange
    agent = AutoModExecutionAgent()
    approved_state["todos"] = [{"agent": "automod_execution", "action": "delete_rule", "params": {"rule_id": 1001}}]
    rule = MagicMock()
    rule.delete = AsyncMock()
    mock_guild.fetch_automod_rule = AsyncMock(return_value=rule)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    assert "1001" in result["details"]
    rule.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_forbidden_error(mock_guild, approved_state):
    # Arrange
    agent = AutoModExecutionAgent()
    approved_state["todos"] = [{"agent": "automod_execution", "action": "create_rule", "params": {"name": "Test", "trigger_type": "keyword", "actions": []}}]
    mock_guild.create_automod_rule = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "No permission"))
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "Missing permissions" in result["details"]


@pytest.mark.asyncio
async def test_not_found_error(mock_guild, approved_state):
    # Arrange
    agent = AutoModExecutionAgent()
    approved_state["todos"] = [{"agent": "automod_execution", "action": "edit_rule", "params": {"rule_id": 99999}}]
    mock_guild.fetch_automod_rule = AsyncMock(side_effect=discord.NotFound(MagicMock(), "Not found"))

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False
    assert "not found" in result["details"].lower()


def test_automod_agent_name():
    agent = AutoModExecutionAgent()
    assert agent.name == "automod_execution"


def test_action_permissions_defined():
    agent = AutoModExecutionAgent()
    assert "create_rule" in agent.ACTION_PERMISSIONS
    assert "manage_guild" in agent.ACTION_PERMISSIONS["create_rule"]
