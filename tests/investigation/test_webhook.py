"""Tests for WebhookInvestigationAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock

from agents.investigation.webhook import WebhookInvestigationAgent
from graph.state import AgentState


@pytest.mark.asyncio
async def test_webhook_list(mock_guild, mock_text_channel, empty_state):
    # Arrange
    agent = WebhookInvestigationAgent()
    
    avatar = MagicMock()
    avatar.url = "https://example.com/webhook_avatar.png"
    
    webhook1 = MagicMock()
    webhook1.id = 2001
    webhook1.name = "Notification Bot"
    webhook1.channel = mock_text_channel
    webhook1.display_avatar = avatar
    webhook1.url = "https://discord.com/api/webhooks/2001/token"
    webhook1.guild_id = 123456
    
    mock_text_channel.webhooks = AsyncMock(return_value=[webhook1])
    mock_guild.text_channels = [mock_text_channel]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert len(result["webhooks"]) == 1
    assert result["webhooks"][0]["name"] == "Notification Bot"
    assert result["webhooks"][0]["avatar_url"] == "https://example.com/webhook_avatar.png"


@pytest.mark.asyncio
async def test_webhook_empty_list(mock_guild, empty_state):
    # Arrange
    agent = WebhookInvestigationAgent()
    
    channel = MagicMock()
    channel.webhooks = AsyncMock(return_value=[])
    
    mock_guild.text_channels = [channel]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["webhooks"] == []
    assert result["total_count"] == 0


@pytest.mark.asyncio
async def test_webhook_no_channels(mock_guild, empty_state):
    # Arrange
    agent = WebhookInvestigationAgent()
    mock_guild.text_channels = []
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["webhooks"] == []
    assert result["total_count"] == 0


@pytest.mark.asyncio
async def test_webhook_no_avatar(mock_guild, mock_text_channel, empty_state):
    # Arrange
    agent = WebhookInvestigationAgent()
    
    webhook = MagicMock()
    webhook.id = 2001
    webhook.name = "Avatarless Bot"
    webhook.channel = mock_text_channel
    webhook.display_avatar = None
    webhook.url = "https://discord.com/api/webhooks/2001/token"
    webhook.guild_id = 123456
    
    mock_text_channel.webhooks = AsyncMock(return_value=[webhook])
    mock_guild.text_channels = [mock_text_channel]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["webhooks"][0]["avatar_url"] is None


@pytest.mark.asyncio
async def test_webhook_agent_name():
    # Arrange & Act
    agent = WebhookInvestigationAgent()
    
    # Assert
    assert agent.name == "webhook_investigation"
