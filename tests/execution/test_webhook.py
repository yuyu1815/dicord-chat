"""Tests for WebhookExecutionAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock

import discord
from agents.execution.webhook import WebhookExecutionAgent
from graph.state import AgentState


@pytest.fixture
def approved_state():
    return {"approved": True, "todos": [], "user_permissions": {}}


@pytest.mark.asyncio
async def test_create_webhook(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = WebhookExecutionAgent()
    approved_state["todos"] = [{"agent": "webhook_execution", "action": "create", "params": {"channel_id": 4001, "name": "Bot Webhook"}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "general"
    webhook = MagicMock()
    webhook.name = "Bot Webhook"
    mock_text_channel.create_webhook = AsyncMock(return_value=webhook)
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Created webhook" in result["details"]


@pytest.mark.asyncio
async def test_create_webhook_channel_not_found(mock_guild, approved_state):
    # Arrange
    agent = WebhookExecutionAgent()
    approved_state["todos"] = [{"agent": "webhook_execution", "action": "create", "params": {"channel_id": 99999, "name": "Test"}}]
    mock_guild.get_channel = MagicMock(return_value=None)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "not found" in result["details"].lower()


@pytest.mark.asyncio
async def test_edit_webhook(mock_guild, approved_state):
    # Arrange
    agent = WebhookExecutionAgent()
    approved_state["todos"] = [{"agent": "webhook_execution", "action": "edit", "params": {"webhook_id": 10001, "name": "Updated"}}]
    webhook = MagicMock()
    webhook.edit = AsyncMock()
    mock_guild.fetch_webhook = AsyncMock(return_value=webhook)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Edited webhook" in result["details"]


@pytest.mark.asyncio
async def test_delete_webhook(mock_guild, approved_state):
    # Arrange
    agent = WebhookExecutionAgent()
    approved_state["todos"] = [{"agent": "webhook_execution", "action": "delete", "params": {"webhook_id": 10001}}]
    webhook = MagicMock()
    webhook.delete = AsyncMock()
    mock_guild.fetch_webhook = AsyncMock(return_value=webhook)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Deleted webhook" in result["details"]


@pytest.mark.asyncio
async def test_execute_webhook(mock_guild, approved_state):
    # Arrange
    agent = WebhookExecutionAgent()
    approved_state["todos"] = [{"agent": "webhook_execution", "action": "execute", "params": {"webhook_id": 10001, "content": "Hello!"}}]
    webhook = MagicMock()
    webhook.send = AsyncMock()
    mock_guild.fetch_webhook = AsyncMock(return_value=webhook)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Executed webhook" in result["details"]


@pytest.mark.asyncio
async def test_forbidden_error(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = WebhookExecutionAgent()
    approved_state["todos"] = [{"agent": "webhook_execution", "action": "create", "params": {"channel_id": 4001, "name": "Test"}}]
    mock_text_channel.create_webhook = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "No permission"))
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "Missing permissions" in result["details"]


def test_webhook_agent_name():
    agent = WebhookExecutionAgent()
    assert agent.name == "webhook_execution"


def test_action_permissions_defined():
    agent = WebhookExecutionAgent()
    assert "create" in agent.ACTION_PERMISSIONS
    assert "manage_webhooks" in agent.ACTION_PERMISSIONS["create"]
