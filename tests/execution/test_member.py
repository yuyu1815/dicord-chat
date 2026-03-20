"""Tests for MemberExecutionAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock

import discord
from agents.execution.member import MemberExecutionAgent
from graph.state import AgentState


@pytest.fixture
def approved_state():
    return {"approved": True, "todos": [], "user_permissions": {}}


@pytest.mark.asyncio
async def test_edit_nickname(mock_guild, approved_state, mock_member):
    # Arrange
    agent = MemberExecutionAgent()
    approved_state["todos"] = [{"agent": "member_execution", "action": "edit_nickname", "params": {"member_id": 2001, "nickname": "NewNick"}}]
    mock_member.id = 2001
    mock_member.display_name = "TestUser"
    mock_member.edit = AsyncMock()
    mock_guild.get_member = MagicMock(return_value=mock_member)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "nickname" in result["details"].lower()


@pytest.mark.asyncio
async def test_edit_nickname_not_found(mock_guild, approved_state):
    # Arrange
    agent = MemberExecutionAgent()
    approved_state["todos"] = [{"agent": "member_execution", "action": "edit_nickname", "params": {"member_id": 99999, "nickname": "Nick"}}]
    mock_guild.get_member = MagicMock(return_value=None)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "not found" in result["details"]


@pytest.mark.asyncio
async def test_timeout_member(mock_guild, approved_state, mock_member):
    # Arrange
    agent = MemberExecutionAgent()
    approved_state["todos"] = [{"agent": "member_execution", "action": "timeout", "params": {"member_id": 2001, "duration_minutes": 60}}]
    mock_member.id = 2001
    mock_member.display_name = "BadUser"
    mock_member.edit = AsyncMock()
    mock_guild.get_member = MagicMock(return_value=mock_member)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "60" in result["details"]


@pytest.mark.asyncio
async def test_kick_member(mock_guild, approved_state, mock_member):
    # Arrange
    agent = MemberExecutionAgent()
    approved_state["todos"] = [{"agent": "member_execution", "action": "kick", "params": {"member_id": 2001, "reason": "Spam"}}]
    mock_member.id = 2001
    mock_member.display_name = "KickedUser"
    mock_member.kick = AsyncMock()
    mock_member.send = AsyncMock()
    mock_guild.get_member = MagicMock(return_value=mock_member)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    assert "Kicked" in result["details"]
    mock_member.send.assert_awaited_once()
    sent_embed = mock_member.send.call_args.kwargs["embed"]
    assert isinstance(sent_embed, discord.Embed)
    assert "Spam" in sent_embed.fields[1].value
    # Arrange
    agent = MemberExecutionAgent()
    approved_state["todos"] = [{"agent": "member_execution", "action": "kick", "params": {"member_id": 2001, "reason": "Spam", "message": "Please follow the rules."}}]
    mock_member.id = 2001
    mock_member.display_name = "KickedUser"
    mock_member.kick = AsyncMock()
    mock_member.send = AsyncMock()
    mock_guild.name = "Test Server"
    mock_guild.get_member = MagicMock(return_value=mock_member)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    assert "notification" in result["details"].lower()
    sent_embed = mock_member.send.call_args.kwargs["embed"]
    assert any(f.value == "Spam" for f in sent_embed.fields)
    assert any(f.value == "Please follow the rules." for f in sent_embed.fields)


@pytest.mark.asyncio
async def test_kick_member_dm_blocked(mock_guild, approved_state, mock_member):
    # Arrange
    agent = MemberExecutionAgent()
    approved_state["todos"] = [{"agent": "member_execution", "action": "kick", "params": {"member_id": 2001, "reason": "Spam"}}]
    mock_member.id = 2001
    mock_member.display_name = "KickedUser"
    mock_member.kick = AsyncMock()
    mock_member.send = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "DM blocked"))
    mock_guild.get_member = MagicMock(return_value=mock_member)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    assert "Kicked" in result["details"]
    assert "notification" not in result["details"].lower()


@pytest.mark.asyncio
async def test_ban_member(mock_guild, approved_state, mock_member):
    # Arrange
    agent = MemberExecutionAgent()
    approved_state["todos"] = [{"agent": "member_execution", "action": "ban", "params": {"member_id": 2001, "reason": "Toxic"}}]
    mock_member.id = 2001
    mock_member.display_name = "BannedUser"
    mock_member.ban = AsyncMock()
    mock_member.send = AsyncMock()
    mock_guild.get_member = MagicMock(return_value=mock_member)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    assert "Banned" in result["details"]
    mock_member.send.assert_awaited_once()
    sent_embed = mock_member.send.call_args.kwargs["embed"]
    assert isinstance(sent_embed, discord.Embed)
    assert "Toxic" in sent_embed.fields[1].value


@pytest.mark.asyncio
async def test_ban_member_with_message(mock_guild, approved_state, mock_member):
    # Arrange
    agent = MemberExecutionAgent()
    approved_state["todos"] = [{"agent": "member_execution", "action": "ban", "params": {"member_id": 2001, "reason": "Toxic", "message": "Appeal in #support if you disagree."}}]
    mock_member.id = 2001
    mock_member.display_name = "BannedUser"
    mock_member.ban = AsyncMock()
    mock_member.send = AsyncMock()
    mock_guild.name = "Test Server"
    mock_guild.get_member = MagicMock(return_value=mock_member)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    assert "notification" in result["details"].lower()
    sent_embed = mock_member.send.call_args.kwargs["embed"]
    assert any(f.value == "Appeal in #support if you disagree." for f in sent_embed.fields)


@pytest.mark.asyncio
async def test_ban_member_no_reason_no_message(mock_guild, approved_state, mock_member):
    # Arrange — reasonもmessageもない場合はDM送信しない
    agent = MemberExecutionAgent()
    approved_state["todos"] = [{"agent": "member_execution", "action": "ban", "params": {"member_id": 2001}}]
    mock_member.id = 2001
    mock_member.display_name = "BannedUser"
    mock_member.ban = AsyncMock()
    mock_member.send = AsyncMock()
    mock_guild.get_member = MagicMock(return_value=mock_member)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    mock_member.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_unban_user(mock_guild, approved_state):
    # Arrange
    agent = MemberExecutionAgent()
    approved_state["todos"] = [{"agent": "member_execution", "action": "unban", "params": {"user_id": 9999}}]
    mock_guild.unban = AsyncMock()
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "9999" in result["details"]


@pytest.mark.asyncio
async def test_edit_roles_add(mock_guild, approved_state, mock_member, mock_role):
    # Arrange
    agent = MemberExecutionAgent()
    approved_state["todos"] = [{"agent": "member_execution", "action": "edit_roles", "params": {"member_id": 2001, "add_roles": [3001]}}]
    mock_member.id = 2001
    mock_member.display_name = "TestUser"
    mock_member.roles = []
    mock_role.id = 3001
    mock_role.name = "Moderator"
    mock_guild.get_member = MagicMock(return_value=mock_member)
    mock_guild.get_role = MagicMock(return_value=mock_role)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "added" in result["details"]


@pytest.mark.asyncio
async def test_edit_roles_remove(mock_guild, approved_state, mock_member, mock_role):
    # Arrange
    agent = MemberExecutionAgent()
    approved_state["todos"] = [{"agent": "member_execution", "action": "edit_roles", "params": {"member_id": 2001, "remove_roles": [3001]}}]
    mock_member.id = 2001
    mock_member.display_name = "TestUser"
    mock_member.roles = [mock_role]
    mock_member.edit = AsyncMock()
    mock_role.id = 3001
    mock_role.name = "Member"
    mock_guild.get_member = MagicMock(return_value=mock_member)
    mock_guild.get_role = MagicMock(return_value=mock_role)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "removed" in result["details"]


@pytest.mark.asyncio
async def test_missing_member_id(mock_guild, approved_state):
    # Arrange
    agent = MemberExecutionAgent()
    approved_state["todos"] = [{"agent": "member_execution", "action": "kick", "params": {}}]
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "Missing" in result["details"]


@pytest.mark.asyncio
async def test_forbidden_error(mock_guild, approved_state, mock_member):
    # Arrange
    agent = MemberExecutionAgent()
    approved_state["todos"] = [{"agent": "member_execution", "action": "kick", "params": {"member_id": 2001}}]
    mock_member.id = 2001
    mock_member.kick = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "No permission"))
    mock_guild.get_member = MagicMock(return_value=mock_member)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "No permission" in result["details"]


def test_member_agent_name():
    agent = MemberExecutionAgent()
    assert agent.name == "member_execution"


def test_action_permissions_defined():
    agent = MemberExecutionAgent()
    assert "kick" in agent.ACTION_PERMISSIONS
    assert "ban_members" in agent.ACTION_PERMISSIONS["ban"]
