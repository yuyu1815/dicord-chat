"""Tests for ThreadInvestigationAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock
import datetime

import discord
from agents.investigation.thread import ThreadInvestigationAgent
from graph.state import AgentState


@pytest.mark.asyncio
async def test_thread_list_investigation(mock_guild, empty_state):
    # Arrange
    agent = ThreadInvestigationAgent()
    
    parent_channel = MagicMock()
    parent_channel.name = "general"
    
    owner = MagicMock()
    owner.name = "ThreadUser"
    
    thread = MagicMock(spec=discord.Thread)
    thread.id = 1001
    thread.name = "Interesting Topic"
    thread.parent = parent_channel
    thread.owner = owner
    thread.member_count = 5
    thread.archived = False
    thread.locked = False
    thread.created_at = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    
    mock_guild.threads = [thread]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["total_count"] == 1
    assert result["threads"][0]["name"] == "Interesting Topic"
    assert result["threads"][0]["parent_channel"] == "general"
    assert result["threads"][0]["owner"] == "ThreadUser"
    assert result["threads"][0]["member_count"] == 5
    assert result["threads"][0]["archived"] is False


@pytest.mark.asyncio
async def test_archived_thread(mock_guild, empty_state):
    # Arrange
    agent = ThreadInvestigationAgent()
    
    parent_channel = MagicMock()
    parent_channel.name = "archive-channel"
    
    thread = MagicMock(spec=discord.Thread)
    thread.id = 1002
    thread.name = "Old Thread"
    thread.parent = parent_channel
    thread.owner = None
    thread.member_count = 0
    thread.archived = True
    thread.locked = True
    thread.created_at = datetime.datetime(2023, 6, 1, tzinfo=datetime.timezone.utc)
    
    mock_guild.threads = [thread]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["threads"][0]["archived"] is True
    assert result["threads"][0]["locked"] is True
    assert result["threads"][0]["owner"] is None


@pytest.mark.asyncio
async def test_thread_without_parent(mock_guild, empty_state):
    # Arrange
    agent = ThreadInvestigationAgent()
    
    thread = MagicMock(spec=discord.Thread)
    thread.id = 1003
    thread.name = "Orphan Thread"
    thread.parent = None
    thread.owner = None
    thread.member_count = 1
    thread.archived = False
    thread.locked = False
    thread.created_at = datetime.datetime(2024, 2, 1, tzinfo=datetime.timezone.utc)
    
    mock_guild.threads = [thread]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["threads"][0]["parent_channel"] is None


@pytest.mark.asyncio
async def test_thread_empty_list(mock_guild, empty_state):
    # Arrange
    agent = ThreadInvestigationAgent()
    mock_guild.threads = []
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["total_count"] == 0
    assert result["threads"] == []


@pytest.mark.asyncio
async def test_thread_agent_name():
    # Arrange & Act
    agent = ThreadInvestigationAgent()
    
    # Assert
    assert agent.name == "thread_investigation"
