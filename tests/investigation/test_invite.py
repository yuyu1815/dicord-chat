"""Tests for InviteInvestigationAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock
import datetime

from agents.investigation.invite import InviteInvestigationAgent
from graph.state import AgentState


@pytest.mark.asyncio
async def test_invite_list(mock_guild, empty_state):
    # Arrange
    agent = InviteInvestigationAgent()
    
    channel = MagicMock()
    channel.name = "general"
    
    inviter = MagicMock()
    inviter.display_name = "Moderator"
    
    invite1 = MagicMock()
    invite1.code = "ABC123"
    invite1.channel = channel
    invite1.inviter = inviter
    invite1.max_uses = 10
    invite1.uses = 5
    invite1.max_age = 86400
    invite1.temporary = False
    invite1.created_at = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    invite1.expires_at = None
    
    invite2 = MagicMock()
    invite2.code = "XYZ789"
    invite2.channel = None
    invite2.inviter = None
    invite2.max_uses = 0
    invite2.uses = 100
    invite2.max_age = 0
    invite2.temporary = True
    invite2.created_at = datetime.datetime(2024, 2, 1, tzinfo=datetime.timezone.utc)
    invite2.expires_at = datetime.datetime(2024, 2, 8, tzinfo=datetime.timezone.utc)
    
    mock_guild.invites = AsyncMock(return_value=[invite1, invite2])
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert len(result["invites"]) == 2
    assert result["invites"][0]["code"] == "ABC123"
    assert result["invites"][0]["channel"] == "general"
    assert result["invites"][0]["inviter"] == "Moderator"
    assert result["invites"][1]["code"] == "XYZ789"
    assert result["invites"][1]["temporary"] is True


@pytest.mark.asyncio
async def test_invite_no_channel(mock_guild, empty_state):
    # Arrange
    agent = InviteInvestigationAgent()
    
    invite = MagicMock()
    invite.code = "TEST01"
    invite.channel = None
    invite.inviter = None
    invite.max_uses = 0
    invite.uses = 0
    invite.max_age = 0
    invite.temporary = False
    invite.created_at = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    invite.expires_at = None
    
    mock_guild.invites = AsyncMock(return_value=[invite])
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["invites"][0]["channel"] is None
    assert result["invites"][0]["inviter"] is None


@pytest.mark.asyncio
async def test_invite_empty_list(mock_guild, empty_state):
    # Arrange
    agent = InviteInvestigationAgent()
    mock_guild.invites = AsyncMock(return_value=[])
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["invites"] == []


@pytest.mark.asyncio
async def test_invite_agent_name():
    # Arrange & Act
    agent = InviteInvestigationAgent()
    
    # Assert
    assert agent.name == "invite_investigation"
