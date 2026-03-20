"""Tests for StickerInvestigationAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock
import datetime

from agents.investigation.sticker import StickerInvestigationAgent
from graph.state import AgentState


@pytest.mark.asyncio
async def test_sticker_list(mock_guild, empty_state):
    # Arrange
    agent = StickerInvestigationAgent()
    
    sticker1 = MagicMock()
    sticker1.id = 1001
    sticker1.name = "hello"
    sticker1.description = "A friendly wave"
    sticker1.format = MagicMock()
    sticker1.format.__str__ = lambda self: "StickerFormatType.png"
    sticker1.tags = "wave, hello, greeting"
    sticker1.available = True
    sticker1.created_at = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    sticker1.pack_id = 500
    
    sticker2 = MagicMock()
    sticker2.id = 1002
    sticker2.name = "bye"
    sticker2.description = "Goodbye!"
    sticker2.format = MagicMock()
    sticker2.format.__str__ = lambda self: "StickerFormatType.lottie"
    sticker2.tags = "bye, goodbye"
    sticker2.available = False
    sticker2.created_at = datetime.datetime(2024, 2, 1, tzinfo=datetime.timezone.utc)
    sticker2.pack_id = 501
    
    mock_guild.stickers = [sticker1, sticker2]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert len(result["stickers"]) == 2
    assert result["stickers"][0]["name"] == "hello"
    assert result["stickers"][0]["available"] is True
    assert result["stickers"][1]["name"] == "bye"
    assert result["stickers"][1]["format_type"] == "StickerFormatType.lottie"


@pytest.mark.asyncio
async def test_sticker_empty_list(mock_guild, empty_state):
    # Arrange
    agent = StickerInvestigationAgent()
    mock_guild.stickers = []
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["stickers"] == []


@pytest.mark.asyncio
async def test_sticker_without_created_at(mock_guild, empty_state):
    # Arrange
    agent = StickerInvestigationAgent()
    
    sticker = MagicMock()
    sticker.id = 1001
    sticker.name = "mystery"
    sticker.description = None
    sticker.format = MagicMock()
    sticker.format.__str__ = lambda self: "StickerFormatType.png"
    sticker.tags = None
    sticker.available = True
    sticker.created_at = None
    sticker.pack_id = None
    
    mock_guild.stickers = [sticker]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["stickers"][0]["created_at"] is None


@pytest.mark.asyncio
async def test_sticker_agent_name():
    # Arrange & Act
    agent = StickerInvestigationAgent()
    
    # Assert
    assert agent.name == "sticker_investigation"
