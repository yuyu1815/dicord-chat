"""Tests for ChannelInvestigationAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock

import discord
from agents.investigation.channel import ChannelInvestigationAgent, MAX_TOPIC_LENGTH
from graph.state import AgentState


@pytest.mark.asyncio
async def test_channel_list_investigation(mock_guild, empty_state):
    # Arrange
    agent = ChannelInvestigationAgent()
    
    text_channel = MagicMock(spec=discord.TextChannel)
    text_channel.id = 1001
    text_channel.name = "general"
    text_channel.type = discord.ChannelType.text
    text_channel.category = None
    text_channel.position = 1
    text_channel.nsfw = False
    text_channel.topic = "General discussion"
    
    voice_channel = MagicMock(spec=discord.VoiceChannel)
    voice_channel.id = 1002
    voice_channel.name = "voice-chat"
    voice_channel.type = discord.ChannelType.voice
    voice_channel.category = None
    voice_channel.position = 1
    voice_channel.nsfw = False
    
    mock_guild.text_channels = [text_channel]
    mock_guild.voice_channels = [voice_channel]
    mock_guild.stage_channels = []
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["total_count"] == 2
    assert len(result["text_channels"]) == 1
    assert len(result["voice_channels"]) == 1
    assert result["text_channels"][0]["name"] == "general"
    assert result["voice_channels"][0]["name"] == "voice-chat"


@pytest.mark.asyncio
async def test_channel_with_category(mock_guild, empty_state):
    # Arrange
    agent = ChannelInvestigationAgent()
    
    category = MagicMock(spec=discord.CategoryChannel)
    category.name = "text-channels"
    
    text_channel = MagicMock(spec=discord.TextChannel)
    text_channel.id = 1001
    text_channel.name = "announcements"
    text_channel.type = discord.ChannelType.text
    text_channel.category = category
    text_channel.position = 1
    text_channel.nsfw = False
    text_channel.topic = None
    
    mock_guild.text_channels = [text_channel]
    mock_guild.voice_channels = []
    mock_guild.stage_channels = []
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["text_channels"][0]["category"] == "text-channels"


@pytest.mark.asyncio
async def test_channel_with_long_topic(mock_guild, empty_state):
    # Arrange
    agent = ChannelInvestigationAgent()
    
    long_topic = "a" * 500
    text_channel = MagicMock(spec=discord.TextChannel)
    text_channel.id = 1001
    text_channel.name = "long-topic"
    text_channel.type = discord.ChannelType.text
    text_channel.category = None
    text_channel.position = 1
    text_channel.nsfw = False
    text_channel.topic = long_topic
    
    mock_guild.text_channels = [text_channel]
    mock_guild.voice_channels = []
    mock_guild.stage_channels = []
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert len(result["text_channels"][0]["topic"]) == MAX_TOPIC_LENGTH


@pytest.mark.asyncio
async def test_nsfw_channel(mock_guild, empty_state):
    # Arrange
    agent = ChannelInvestigationAgent()
    
    text_channel = MagicMock(spec=discord.TextChannel)
    text_channel.id = 1001
    text_channel.name = "nsfw-channel"
    text_channel.type = discord.ChannelType.text
    text_channel.category = None
    text_channel.position = 1
    text_channel.nsfw = True
    text_channel.topic = None
    
    mock_guild.text_channels = [text_channel]
    mock_guild.voice_channels = []
    mock_guild.stage_channels = []
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["text_channels"][0]["nsfw"] is True


@pytest.mark.asyncio
async def test_channel_empty_lists(mock_guild, empty_state):
    # Arrange
    agent = ChannelInvestigationAgent()
    mock_guild.text_channels = []
    mock_guild.voice_channels = []
    mock_guild.stage_channels = []
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["total_count"] == 0
    assert result["text_channels"] == []
    assert result["voice_channels"] == []
    assert result["stage_channels"] == []


@pytest.mark.asyncio
async def test_channel_agent_name():
    # Arrange & Act
    agent = ChannelInvestigationAgent()
    
    # Assert
    assert agent.name == "channel_investigation"
