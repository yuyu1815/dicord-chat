"""Tests for MemberInvestigationAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock
import datetime

import discord
from agents.investigation.member import MemberInvestigationAgent, DEFAULT_MEMBER_LIMIT
from graph.state import AgentState


@pytest.mark.asyncio
async def test_member_list_investigation(mock_guild, empty_state):
    # Arrange
    agent = MemberInvestigationAgent()
    member1 = MagicMock(spec=discord.Member)
    member1.id = 1001
    member1.name = "Alice"
    member1.display_name = "AliceDisplay"
    member1.nick = None
    member1.top_role = MagicMock()
    member1.top_role.name = "Member"
    member1.joined_at = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    member1.bot = False

    member2 = MagicMock(spec=discord.Member)
    member2.id = 1002
    member2.name = "Bob"
    member2.display_name = "BobDisplay"
    member2.nick = "BobNick"
    member2.top_role = MagicMock()
    member2.top_role.name = "Moderator"
    member2.joined_at = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc)
    member2.bot = False

    async def mock_fetch_members(limit):
        yield member1
        yield member2

    mock_guild.fetch_members = mock_fetch_members
    mock_guild.member_count = 2
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["fetched_count"] == 2
    assert result["total_members"] == 2
    assert len(result["members"]) == 2
    assert result["members"][0]["name"] == "Alice"
    assert result["members"][1]["name"] == "Bob"


@pytest.mark.asyncio
async def test_single_member_investigation(mock_guild, empty_state):
    # Arrange
    agent = MemberInvestigationAgent()
    
    member = MagicMock(spec=discord.Member)
    member.id = 3001
    member.name = "TargetUser"
    member.display_name = "TargetDisplay"
    member.nick = "TargetNick"
    member.display_avatar = MagicMock()
    member.display_avatar.url = "https://example.com/avatar.png"
    member.joined_at = datetime.datetime(2024, 1, 15, tzinfo=datetime.timezone.utc)
    member.created_at = datetime.datetime(2023, 6, 1, tzinfo=datetime.timezone.utc)
    member.top_role = MagicMock()
    member.top_role.name = "Admin"
    role1 = MagicMock()
    role1.name = "Admin"
    role1.is_default = MagicMock(return_value=False)
    role2 = MagicMock()
    role2.name = "@everyone"
    role2.is_default = MagicMock(return_value=True)
    member.roles = [role1, role2]
    member.status = discord.Status.online
    member.activities = []
    member.bot = False
    
    mock_guild.get_member = MagicMock(return_value=member)
    state: AgentState = {**empty_state, "user_id": 3001}
    
    # Act
    result = await agent.investigate(state, mock_guild)
    
    # Assert
    assert result["id"] == 3001
    assert result["name"] == "TargetUser"
    assert result["display_name"] == "TargetDisplay"
    assert result["nick"] == "TargetNick"
    assert result["top_role"] == "Admin"
    assert "Admin" in result["roles"]
    assert "@everyone" not in result["roles"]


class MockError(Exception):
    """Mock error for testing."""
    pass


class MockResponse:
    """Mock response for discord.NotFound."""
    def __init__(self):
        self.status = 404
        self.reason = "Not Found"


@pytest.mark.asyncio
async def test_single_member_not_found(mock_guild, empty_state):
    # Arrange
    agent = MemberInvestigationAgent()
    
    mock_guild.get_member = MagicMock(return_value=None)
    mock_guild.fetch_member = AsyncMock(side_effect=discord.NotFound(MockResponse(), "Not found"))
    state: AgentState = {**empty_state, "user_id": 99999}
    
    # Act
    result = await agent.investigate(state, mock_guild)
    
    # Assert
    assert "error" in result
    assert "99999" in result["error"]


@pytest.mark.asyncio
async def test_member_investigation_with_activity(mock_guild, empty_state):
    # Arrange
    agent = MemberInvestigationAgent()
    
    member = MagicMock(spec=discord.Member)
    member.id = 4001
    member.name = "GamerUser"
    member.display_name = "Gamer"
    member.nick = None
    member.display_avatar = MagicMock()
    member.display_avatar.url = "https://example.com/avatar2.png"
    member.joined_at = datetime.datetime(2024, 2, 1, tzinfo=datetime.timezone.utc)
    member.created_at = datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc)
    member.top_role = MagicMock()
    member.top_role.name = "Member"
    member.roles = []
    member.status = discord.Status.online
    activity = MagicMock(spec=discord.BaseActivity)
    activity.name = "Overwatch"
    activity.type = discord.ActivityType.playing
    member.activities = [activity]
    member.bot = False
    
    mock_guild.get_member = MagicMock(return_value=member)
    state: AgentState = {**empty_state, "user_id": 4001}
    
    # Act
    result = await agent.investigate(state, mock_guild)
    
    # Assert
    assert result["activity"]["name"] == "Overwatch"
    assert result["activity"]["type"] == "ActivityType.playing"


@pytest.mark.asyncio
async def test_member_agent_name():
    # Arrange & Act
    agent = MemberInvestigationAgent()
    
    # Assert
    assert agent.name == "member_investigation"
