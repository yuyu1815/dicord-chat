"""Tests for StageInvestigationAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock

import discord
from agents.investigation.stage import StageInvestigationAgent
from graph.state import AgentState


@pytest.mark.asyncio
async def test_stage_channel_list(mock_guild, empty_state):
    # Arrange
    agent = StageInvestigationAgent()
    
    stage = MagicMock(spec=discord.StageChannel)
    stage.id = 1001
    stage.name = "Community Talk"
    stage.topic = "Weekly discussion"
    stage.category = None
    stage.bitrate = 64000
    stage.members = []
    stage.stage_instance = None
    
    mock_guild.stage_channels = [stage]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["stages"][0]["name"] == "Community Talk"
    assert result["stages"][0]["topic"] == "Weekly discussion"
    assert result["stages"][0]["stage_instance_active"] is False


@pytest.mark.asyncio
async def test_stage_with_active_instance(mock_guild, empty_state):
    # Arrange
    agent = StageInvestigationAgent()
    
    member1 = MagicMock()
    member1.display_name = "Speaker1"
    member2 = MagicMock()
    member2.display_name = "Listener"
    
    stage_instance = MagicMock()
    stage_instance.speakers = [member1]
    stage_instance.topic = "Live Stage"
    
    stage = MagicMock(spec=discord.StageChannel)
    stage.id = 1001
    stage.name = "Main Stage"
    stage.topic = None
    stage.category = None
    stage.bitrate = 128000
    stage.members = [member1, member2]
    stage.stage_instance = stage_instance
    
    mock_guild.stage_channels = [stage]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["stages"][0]["stage_instance_active"] is True
    assert result["stages"][0]["speaker_count"] == 1
    assert len(result["stages"][0]["current_members"]) == 2


@pytest.mark.asyncio
async def test_stage_empty_list(mock_guild, empty_state):
    # Arrange
    agent = StageInvestigationAgent()
    mock_guild.stage_channels = []
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["stages"] == []


@pytest.mark.asyncio
async def test_stage_with_category(mock_guild, empty_state):
    # Arrange
    agent = StageInvestigationAgent()
    
    category = MagicMock()
    category.name = "Events"
    
    stage = MagicMock(spec=discord.StageChannel)
    stage.id = 1001
    stage.name = "Event Stage"
    stage.topic = None
    stage.category = category
    stage.bitrate = 64000
    stage.members = []
    stage.stage_instance = None
    
    mock_guild.stage_channels = [stage]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["stages"][0]["category"] == "Events"


@pytest.mark.asyncio
async def test_stage_agent_name():
    # Arrange & Act
    agent = StageInvestigationAgent()
    
    # Assert
    assert agent.name == "stage_investigation"
