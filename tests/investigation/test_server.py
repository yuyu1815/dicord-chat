"""Tests for ServerInvestigationAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock
import datetime

import discord
from agents.investigation.server import ServerInvestigationAgent
from graph.state import AgentState


@pytest.mark.asyncio
async def test_server_investigation_returns_basic_info(mock_guild, empty_state):
    # Arrange
    agent = ServerInvestigationAgent()
    mock_guild.name = "My Awesome Server"
    mock_guild.id = 987654321
    mock_guild.owner_id = 111222333
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["name"] == "My Awesome Server"
    assert result["id"] == 987654321
    assert result["owner_id"] == 111222333


@pytest.mark.asyncio
async def test_server_investigation_includes_member_count(mock_guild, empty_state):
    # Arrange
    agent = ServerInvestigationAgent()
    mock_guild.member_count = 42
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["member_count"] == 42


@pytest.mark.asyncio
async def test_server_investigation_includes_verification_level(mock_guild, empty_state):
    # Arrange
    agent = ServerInvestigationAgent()
    mock_guild.verification_level = discord.VerificationLevel.high
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert "high" in result["verification_level"]


@pytest.mark.asyncio
async def test_server_investigation_includes_features(mock_guild, empty_state):
    # Arrange
    agent = ServerInvestigationAgent()
    mock_guild.features = ["COMMUNITY", "NEWS", "ANIMATED_ICON"]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert "COMMUNITY" in result["features"]
    assert "NEWS" in result["features"]
    assert "ANIMATED_ICON" in result["features"]


@pytest.mark.asyncio
async def test_server_investigation_with_icon(mock_guild, empty_state):
    # Arrange
    agent = ServerInvestigationAgent()
    mock_icon = MagicMock()
    mock_icon.url = "https://cdn.discord.com/icons/123/avatar.png"
    mock_guild.icon = mock_icon
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["icon_url"] == "https://cdn.discord.com/icons/123/avatar.png"


@pytest.mark.asyncio
async def test_server_investigation_without_icon(mock_guild, empty_state):
    # Arrange
    agent = ServerInvestigationAgent()
    mock_guild.icon = None
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["icon_url"] is None


@pytest.mark.asyncio
async def test_server_investigation_with_system_channel(mock_guild, empty_state):
    # Arrange
    agent = ServerInvestigationAgent()
    mock_channel = MagicMock()
    mock_channel.name = "system-messages"
    mock_guild.system_channel = mock_channel
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["system_channel"] == "system-messages"


@pytest.mark.asyncio
async def test_server_investigation_agent_name():
    # Arrange & Act
    agent = ServerInvestigationAgent()
    
    # Assert
    assert agent.name == "server_investigation"
