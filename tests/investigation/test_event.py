"""Tests for EventInvestigationAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock
import datetime

from agents.investigation.event import EventInvestigationAgent
from graph.state import AgentState


@pytest.mark.asyncio
async def test_event_list(mock_guild, empty_state):
    # Arrange
    agent = EventInvestigationAgent()
    
    creator = MagicMock()
    creator.display_name = "EventAdmin"
    
    event = MagicMock()
    event.id = 1001
    event.name = "Community Meeting"
    event.description = "Monthly community discussion"
    event.start_time = datetime.datetime(2024, 2, 1, 12, 0, tzinfo=datetime.timezone.utc)
    event.end_time = datetime.datetime(2024, 2, 1, 14, 0, tzinfo=datetime.timezone.utc)
    event.location = MagicMock()
    event.location.__str__ = lambda self: "Voice Channel"
    event.creator = creator
    event.status = MagicMock()
    event.status.__str__ = lambda self: "EventStatus.scheduled"
    event.subscriber_count = 50
    event.cover = None
    
    mock_guild.scheduled_events = [event]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert len(result["events"]) == 1
    assert result["events"][0]["name"] == "Community Meeting"
    assert result["events"][0]["creator"] == "EventAdmin"
    assert result["events"][0]["subscriber_count"] == 50


@pytest.mark.asyncio
async def test_event_with_cover_image(mock_guild, empty_state):
    # Arrange
    agent = EventInvestigationAgent()
    
    cover = MagicMock()
    cover.url = "https://example.com/cover.png"
    
    event = MagicMock()
    event.id = 1001
    event.name = "Concert"
    event.description = "Live music"
    event.start_time = datetime.datetime(2024, 3, 1, 19, 0, tzinfo=datetime.timezone.utc)
    event.end_time = None
    event.location = None
    event.creator = None
    event.status = MagicMock()
    event.status.__str__ = lambda self: "EventStatus.active"
    event.subscriber_count = 100
    event.cover = cover
    
    mock_guild.scheduled_events = [event]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["events"][0]["image_url"] == "https://example.com/cover.png"


@pytest.mark.asyncio
async def test_event_truncated_description(mock_guild, empty_state):
    # Arrange
    agent = EventInvestigationAgent()
    
    long_description = "a" * 300
    event = MagicMock()
    event.id = 1001
    event.name = "Long Event"
    event.description = long_description
    event.start_time = datetime.datetime(2024, 2, 1, tzinfo=datetime.timezone.utc)
    event.end_time = None
    event.location = None
    event.creator = None
    event.status = MagicMock()
    event.status.__str__ = lambda self: "EventStatus.scheduled"
    event.subscriber_count = 0
    event.cover = None
    
    mock_guild.scheduled_events = [event]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert len(result["events"][0]["description"]) == 203  # 200 + "..."


@pytest.mark.asyncio
async def test_event_empty_list(mock_guild, empty_state):
    # Arrange
    agent = EventInvestigationAgent()
    mock_guild.scheduled_events = []
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["events"] == []


@pytest.mark.asyncio
async def test_event_agent_name():
    # Arrange & Act
    agent = EventInvestigationAgent()
    
    # Assert
    assert agent.name == "event_investigation"
