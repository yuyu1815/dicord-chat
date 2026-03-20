"""Tests for ForumInvestigationAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock

import discord
from agents.investigation.forum import ForumInvestigationAgent
from graph.state import AgentState


@pytest.mark.asyncio
async def test_forum_list_investigation(mock_guild, empty_state):
    # Arrange
    agent = ForumInvestigationAgent()
    
    tag1 = MagicMock()
    tag1.id = 101
    tag1.name = "Question"
    tag1.emoji = "❓"
    tag1.moderated = True
    
    tag2 = MagicMock()
    tag2.id = 102
    tag2.name = "Announcement"
    tag2.emoji = None
    tag2.moderated = False
    
    forum = MagicMock(spec=discord.ForumChannel)
    forum.id = 2001
    forum.name = "Support Forum"
    forum.topic = "Get help here"
    forum.available_tags = [tag1, tag2]
    
    other_channel = MagicMock()
    other_channel.__class__ = discord.TextChannel
    
    mock_guild.channels = [forum, other_channel]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["total_count"] == 1
    assert result["forums"][0]["name"] == "Support Forum"
    assert result["forums"][0]["topic"] == "Get help here"
    assert len(result["forums"][0]["tags"]) == 2
    assert result["forums"][0]["tags"][0]["name"] == "Question"


@pytest.mark.asyncio
async def test_forum_with_emoji_tags(mock_guild, empty_state):
    # Arrange
    agent = ForumInvestigationAgent()
    
    tag = MagicMock()
    tag.id = 101
    tag.name = "Bug"
    tag.emoji = MagicMock()
    tag.emoji.__str__ = lambda self: "🐛"
    tag.moderated = False
    
    forum = MagicMock(spec=discord.ForumChannel)
    forum.id = 2001
    forum.name = "Bug Reports"
    forum.topic = None
    forum.available_tags = [tag]
    
    mock_guild.channels = [forum]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["forums"][0]["tags"][0]["emoji"] == "🐛"
    assert result["forums"][0]["tags"][0]["moderated"] is False


@pytest.mark.asyncio
async def test_forum_empty_list(mock_guild, empty_state):
    # Arrange
    agent = ForumInvestigationAgent()
    mock_guild.channels = []
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["total_count"] == 0
    assert result["forums"] == []


@pytest.mark.asyncio
async def test_forum_no_tags(mock_guild, empty_state):
    # Arrange
    agent = ForumInvestigationAgent()
    
    forum = MagicMock(spec=discord.ForumChannel)
    forum.id = 2001
    forum.name = "Empty Forum"
    forum.topic = None
    forum.available_tags = []
    
    mock_guild.channels = [forum]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["forums"][0]["tags"] == []


@pytest.mark.asyncio
async def test_forum_agent_name():
    # Arrange & Act
    agent = ForumInvestigationAgent()
    
    # Assert
    assert agent.name == "forum_investigation"
