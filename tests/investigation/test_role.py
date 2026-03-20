"""Tests for RoleInvestigationAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock

import discord
from agents.investigation.role import RoleInvestigationAgent, KEY_PERMISSIONS
from graph.state import AgentState


@pytest.mark.asyncio
async def test_role_list_investigation(mock_guild, empty_state):
    # Arrange
    agent = RoleInvestigationAgent()
    
    role1 = MagicMock(spec=discord.Role)
    role1.id = 1001
    role1.name = "Admin"
    role1.color = discord.Color.red()
    role1.position = 10
    role1.mentionable = True
    role1.managed = False
    role1.permissions = MagicMock()
    role1.permissions.administrator = True
    role1.permissions.manage_guild = True
    role1.permissions.manage_channels = True
    role1.permissions.kick_members = True
    role1.permissions.ban_members = True
    role1.permissions.mention_everyone = True
    role1.permissions.hoist = True
    role1.members = []
    
    role2 = MagicMock(spec=discord.Role)
    role2.id = 1002
    role2.name = "Member"
    role2.color = discord.Color.default()
    role2.position = 1
    role2.mentionable = False
    role2.managed = False
    role2.permissions = MagicMock()
    role2.permissions.administrator = False
    role2.permissions.manage_guild = False
    role2.permissions.manage_channels = False
    role2.permissions.kick_members = False
    role2.permissions.ban_members = False
    role2.permissions.mention_everyone = False
    role2.permissions.hoist = False
    role2.members = []
    
    mock_guild.roles = [role1, role2]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["total_count"] == 2
    assert len(result["roles"]) == 2
    assert result["roles"][0]["name"] == "Admin"
    assert result["roles"][0]["permissions"]["administrator"] is True
    assert result["roles"][1]["name"] == "Member"
    assert result["roles"][1]["permissions"]["administrator"] is False


@pytest.mark.asyncio
async def test_role_includes_member_count(mock_guild, empty_state):
    # Arrange
    agent = RoleInvestigationAgent()
    
    member = MagicMock()
    role = MagicMock(spec=discord.Role)
    role.id = 1001
    role.name = "TestRole"
    role.color = discord.Color.blue()
    role.position = 5
    role.mentionable = True
    role.managed = False
    role.permissions = MagicMock()
    for perm in KEY_PERMISSIONS:
        setattr(role.permissions, perm, False)
    role.members = [member, member, member]
    
    mock_guild.roles = [role]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["roles"][0]["member_count"] == 3


@pytest.mark.asyncio
async def test_role_managed_flag(mock_guild, empty_state):
    # Arrange
    agent = RoleInvestigationAgent()
    
    role = MagicMock(spec=discord.Role)
    role.id = 1001
    role.name = "BotRole"
    role.color = discord.Color.default()
    role.position = 1
    role.mentionable = False
    role.managed = True
    role.permissions = MagicMock()
    for perm in KEY_PERMISSIONS:
        setattr(role.permissions, perm, False)
    role.members = []
    
    mock_guild.roles = [role]
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["roles"][0]["managed"] is True


@pytest.mark.asyncio
async def test_role_empty_list(mock_guild, empty_state):
    # Arrange
    agent = RoleInvestigationAgent()
    mock_guild.roles = []
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["total_count"] == 0
    assert result["roles"] == []


@pytest.mark.asyncio
async def test_role_agent_name():
    # Arrange & Act
    agent = RoleInvestigationAgent()
    
    # Assert
    assert agent.name == "role_investigation"
