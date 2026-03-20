"""Tests for SoundboardInvestigationAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock

from agents.investigation.soundboard import SoundboardInvestigationAgent
from graph.state import AgentState


@pytest.mark.asyncio
async def test_soundboard_list(mock_guild, empty_state):
    # Arrange
    agent = SoundboardInvestigationAgent()
    
    creator = MagicMock()
    creator.display_name = "SoundAdmin"
    
    sound1 = MagicMock()
    sound1.id = 1001
    sound1.name = "applause"
    sound1.emoji = "👏"
    sound1.volume = 1.0
    sound1.available = True
    sound1.user = creator
    sound1.guild_id = 123456
    
    sound2 = MagicMock()
    sound2.id = 1002
    sound2.name = "drumroll"
    sound2.emoji = "🥁"
    sound2.volume = 0.5
    sound2.available = False
    sound2.user = None
    sound2.guild_id = 123456
    
    mock_guild.soundboard_sounds = [sound1, sound2]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert len(result["soundboard_sounds"]) == 2
    assert result["soundboard_sounds"][0]["name"] == "applause"
    assert result["soundboard_sounds"][0]["creator"] == "SoundAdmin"
    assert result["soundboard_sounds"][1]["name"] == "drumroll"
    assert result["soundboard_sounds"][1]["volume"] == 0.5


@pytest.mark.asyncio
async def test_soundboard_empty_list(mock_guild, empty_state):
    # Arrange
    agent = SoundboardInvestigationAgent()
    mock_guild.soundboard_sounds = []
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["soundboard_sounds"] == []
    assert result["total_count"] == 0


@pytest.mark.asyncio
async def test_soundboard_no_creator(mock_guild, empty_state):
    # Arrange
    agent = SoundboardInvestigationAgent()
    
    sound = MagicMock()
    sound.id = 1001
    sound.name = "test_sound"
    sound.emoji = "🔊"
    sound.volume = 0.8
    sound.available = True
    sound.user = None
    sound.guild_id = 123456
    
    mock_guild.soundboard_sounds = [sound]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["soundboard_sounds"][0]["creator"] is None


@pytest.mark.asyncio
async def test_soundboard_agent_name():
    # Arrange & Act
    agent = SoundboardInvestigationAgent()
    
    # Assert
    assert agent.name == "soundboard_investigation"
