"""Tests for EmojiInvestigationAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock

from agents.investigation.emoji import EmojiInvestigationAgent
from graph.state import AgentState


@pytest.mark.asyncio
async def test_emoji_list(mock_guild, empty_state):
    # Arrange
    agent = EmojiInvestigationAgent()
    
    role1 = MagicMock()
    role1.name = "Subscriber"
    role2 = MagicMock()
    role2.name = "VIP"
    
    creator = MagicMock()
    creator.display_name = "AdminUser"
    
    emoji1 = MagicMock()
    emoji1.id = 1001
    emoji1.name = "smile"
    emoji1.animated = False
    emoji1.managed = False
    emoji1.roles = [role1]
    emoji1.user = creator
    
    emoji2 = MagicMock()
    emoji2.id = 1002
    emoji2.name = "dance"
    emoji2.animated = True
    emoji2.managed = True
    emoji2.roles = [role1, role2]
    emoji2.user = None
    
    mock_guild.emojis = [emoji1, emoji2]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert len(result["emojis"]) == 2
    assert result["emojis"][0]["name"] == "smile"
    assert result["emojis"][0]["animated"] is False
    assert result["emojis"][0]["creator"] == "AdminUser"
    assert result["emojis"][1]["name"] == "dance"
    assert result["emojis"][1]["animated"] is True
    assert result["emojis"][1]["managed"] is True


@pytest.mark.asyncio
async def test_emoji_empty_list(mock_guild, empty_state):
    # Arrange
    agent = EmojiInvestigationAgent()
    mock_guild.emojis = []
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["emojis"] == []


@pytest.mark.asyncio
async def test_emoji_role_restricted(mock_guild, empty_state):
    # Arrange
    agent = EmojiInvestigationAgent()
    
    role = MagicMock()
    role.name = "Premium"
    
    emoji = MagicMock()
    emoji.id = 1001
    emoji.name = "premium_emoji"
    emoji.animated = False
    emoji.managed = False
    emoji.roles = [role]
    emoji.user = None
    
    mock_guild.emojis = [emoji]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["emojis"][0]["roles"] == ["Premium"]


@pytest.mark.asyncio
async def test_emoji_agent_name():
    # Arrange & Act
    agent = EmojiInvestigationAgent()
    
    # Assert
    assert agent.name == "emoji_investigation"
