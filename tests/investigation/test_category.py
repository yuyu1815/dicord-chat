"""Tests for CategoryInvestigationAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock

import discord
from agents.investigation.category import CategoryInvestigationAgent
from graph.state import AgentState


@pytest.mark.asyncio
async def test_category_list_investigation(mock_guild, empty_state):
    # Arrange
    agent = CategoryInvestigationAgent()
    
    channel1 = MagicMock()
    channel1.name = "general"
    channel2 = MagicMock()
    channel2.name = "announcements"
    channel3 = MagicMock()
    channel3.name = "voice-chat"
    
    category1 = MagicMock(spec=discord.CategoryChannel)
    category1.id = 1001
    category1.name = "Text Channels"
    category1.position = 1
    category1.channels = [channel1, channel2]
    
    category2 = MagicMock(spec=discord.CategoryChannel)
    category2.id = 1002
    category2.name = "Voice Channels"
    category2.position = 2
    category2.channels = [channel3]
    
    mock_guild.categories = [category1, category2]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["total_count"] == 2
    assert result["categories"][0]["name"] == "Text Channels"
    assert result["categories"][0]["channel_count"] == 2
    assert "general" in result["categories"][0]["channels"]
    assert result["categories"][1]["name"] == "Voice Channels"
    assert len(result["categories"][1]["channels"]) == 1


@pytest.mark.asyncio
async def test_category_empty_list(mock_guild, empty_state):
    # Arrange
    agent = CategoryInvestigationAgent()
    mock_guild.categories = []
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["total_count"] == 0
    assert result["categories"] == []


@pytest.mark.asyncio
async def test_category_positions(mock_guild, empty_state):
    # Arrange
    agent = CategoryInvestigationAgent()
    
    channel = MagicMock()
    channel.name = "test"
    
    cat1 = MagicMock(spec=discord.CategoryChannel)
    cat1.id = 1001
    cat1.name = "First"
    cat1.position = 2
    cat1.channels = [channel]
    
    cat2 = MagicMock(spec=discord.CategoryChannel)
    cat2.id = 1002
    cat2.name = "Second"
    cat2.position = 1
    cat2.channels = []
    
    mock_guild.categories = [cat1, cat2]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["categories"][0]["position"] == 2


@pytest.mark.asyncio
async def test_category_agent_name():
    # Arrange & Act
    agent = CategoryInvestigationAgent()
    
    # Assert
    assert agent.name == "category_investigation"
