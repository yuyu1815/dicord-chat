"""Tests for PermissionInvestigationAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock

import discord
from agents.investigation.permission import PermissionInvestigationAgent, KEY_PERMISSIONS
from graph.state import AgentState


@pytest.mark.asyncio
async def test_guild_level_permissions(mock_guild, empty_state):
    # Arrange
    agent = PermissionInvestigationAgent()
    
    role1 = MagicMock(spec=discord.Role)
    role1.id = 1001
    role1.name = "Admin"
    role1.permissions = MagicMock()
    role1.permissions.administrator = True
    role1.permissions.manage_guild = True
    role1.permissions.manage_channels = True
    role1.permissions.manage_messages = True
    role1.permissions.manage_roles = True
    role1.permissions.kick_members = True
    role1.permissions.ban_members = True
    role1.permissions.send_messages = True
    role1.permissions.read_messages = True
    role1.permissions.connect = True
    role1.permissions.speak = True
    
    role2 = MagicMock(spec=discord.Role)
    role2.id = 1002
    role2.name = "Member"
    role2.permissions = MagicMock()
    role2.permissions.administrator = False
    role2.permissions.manage_guild = False
    role2.permissions.manage_channels = False
    role2.permissions.manage_messages = False
    role2.permissions.manage_roles = False
    role2.permissions.kick_members = False
    role2.permissions.ban_members = False
    role2.permissions.send_messages = True
    role2.permissions.read_messages = True
    role2.permissions.connect = True
    role2.permissions.speak = True
    
    mock_guild.roles = [role1, role2]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)  # No channel_id
    
    # Assert
    assert result["scope"] == "guild"
    assert len(result["roles"]) == 2
    assert result["roles"][0]["role_name"] == "Admin"
    assert result["roles"][0]["permissions"]["administrator"] is True


@pytest.mark.asyncio
async def test_channel_overwrites(mock_guild, mock_text_channel, empty_state):
    # Arrange
    agent = PermissionInvestigationAgent()
    
    role = MagicMock(spec=discord.Role)
    role.id = 1001
    role.name = "Muted"
    
    allow_perms = MagicMock()
    allow_perms.__iter__ = lambda self: iter([])
    allowed = []
    
    deny_perms = MagicMock()
    deny_perms.__iter__ = lambda self: iter([("send_messages", True)])
    denied = ["send_messages"]
    
    overwrite = MagicMock()
    overwrite_pair = (allow_perms, deny_perms)
    overwrite.pair = MagicMock(return_value=overwrite_pair)
    
    mock_text_channel.id = 4001
    mock_text_channel.name = "mod-only"
    mock_text_channel.overwrites = {role: overwrite}
    
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    
    state: AgentState = {**empty_state, "channel_id": 4001}
    
    # Act
    result = await agent.investigate(state, mock_guild)
    
    # Assert
    assert result["scope"] == "channel"
    assert result["channel_name"] == "mod-only"
    assert len(result["overwrites"]) == 1
    assert result["overwrites"][0]["target_name"] == "Muted"
    assert result["overwrites"][0]["target_type"] == "role"


@pytest.mark.asyncio
async def test_permission_channel_not_found(mock_guild, empty_state):
    # Arrange
    agent = PermissionInvestigationAgent()
    mock_guild.get_channel = MagicMock(return_value=None)
    
    state: AgentState = {**empty_state, "channel_id": 99999}
    
    # Act
    result = await agent.investigate(state, mock_guild)
    
    # Assert
    assert "error" in result
    assert "99999" in result["error"]


@pytest.mark.asyncio
async def test_permission_agent_name():
    # Arrange & Act
    agent = PermissionInvestigationAgent()
    
    # Assert
    assert agent.name == "permission_investigation"
