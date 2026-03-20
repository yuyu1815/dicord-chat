"""Tests for VCInvestigationAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock

import discord
from agents.investigation.vc import VCInvestigationAgent
from graph.state import AgentState


@pytest.mark.asyncio
async def test_voice_channel_list(mock_guild, empty_state):
    # Arrange
    agent = VCInvestigationAgent()
    
    category = MagicMock()
    category.name = "Voice Channels"
    
    vc1 = MagicMock(spec=discord.VoiceChannel)
    vc1.id = 1001
    vc1.name = "General"
    vc1.category = category
    vc1.position = 1
    vc1.bitrate = 64000
    vc1.user_limit = 10
    vc1.members = []
    vc1.nsfw = False
    
    vc2 = MagicMock(spec=discord.VoiceChannel)
    vc2.id = 1002
    vc2.name = "Gaming"
    vc2.category = None
    vc2.position = 2
    vc2.bitrate = 128000
    vc2.user_limit = 20
    vc2.members = []
    vc2.nsfw = True
    
    mock_guild.voice_channels = [vc1, vc2]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["total_count"] == 2
    assert result["voice_channels"][0]["name"] == "General"
    assert result["voice_channels"][0]["bitrate"] == 64000
    assert result["voice_channels"][1]["name"] == "Gaming"
    assert result["voice_channels"][1]["nsfw"] is True


@pytest.mark.asyncio
async def test_voice_channel_with_members(mock_guild, empty_state):
    # Arrange
    agent = VCInvestigationAgent()
    
    member1 = MagicMock(spec=discord.Member)
    member1.display_name = "Alice"
    member1.voice = MagicMock()
    member1.voice.mute = False
    member1.voice.deaf = False
    member1.voice.self_mute = True
    member1.voice.self_deaf = False
    member1.voice.self_stream = False
    
    member2 = MagicMock(spec=discord.Member)
    member2.display_name = "Bob"
    member2.voice = MagicMock()
    member2.voice.mute = True
    member2.voice.deaf = False
    member2.voice.self_mute = False
    member2.voice.self_deaf = True
    member2.voice.self_stream = True
    
    vc = MagicMock(spec=discord.VoiceChannel)
    vc.id = 1001
    vc.name = "Chat"
    vc.category = None
    vc.position = 1
    vc.bitrate = 64000
    vc.user_limit = 0
    vc.members = [member1, member2]
    vc.nsfw = False
    
    mock_guild.voice_channels = [vc]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["voice_channels"][0]["member_count"] == 2
    assert result["voice_channels"][0]["current_members"][0]["name"] == "Alice"
    assert result["voice_channels"][0]["current_members"][0]["self_muted"] is True
    assert result["voice_channels"][0]["current_members"][1]["streaming"] is True


@pytest.mark.asyncio
async def test_voice_channel_empty(mock_guild, empty_state):
    # Arrange
    agent = VCInvestigationAgent()
    mock_guild.voice_channels = []
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["total_count"] == 0
    assert result["voice_channels"] == []


@pytest.mark.asyncio
async def test_voice_channel_member_no_voice(mock_guild, empty_state):
    # Arrange
    agent = VCInvestigationAgent()
    
    member = MagicMock(spec=discord.Member)
    member.display_name = "Offline User"
    member.voice = None
    
    vc = MagicMock(spec=discord.VoiceChannel)
    vc.id = 1001
    vc.name = "Empty"
    vc.category = None
    vc.position = 1
    vc.bitrate = 64000
    vc.user_limit = 10
    vc.members = [member]
    vc.nsfw = False
    
    mock_guild.voice_channels = [vc]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["voice_channels"][0]["current_members"][0]["muted"] is False
    assert result["voice_channels"][0]["current_members"][0]["deafened"] is False


@pytest.mark.asyncio
async def test_voice_agent_name():
    # Arrange & Act
    agent = VCInvestigationAgent()
    
    # Assert
    assert agent.name == "vc_investigation"
