"""Tests for AuditLogInvestigationAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock
import datetime

from agents.investigation.audit_log import AuditLogInvestigationAgent, MAX_DEFAULT_ENTRIES
from graph.state import AgentState


def _make_async_iterator(items):
    """Helper to create async generator for audit_logs."""
    async def iterator(limit=None):
        for item in items:
            yield item
    return iterator()


@pytest.mark.asyncio
async def test_audit_log_list(mock_guild, empty_state):
    # Arrange
    agent = AuditLogInvestigationAgent()
    
    target = MagicMock()
    target.display_name = "TestUser"
    
    user = MagicMock()
    user.display_name = "AdminUser"
    
    entry1 = MagicMock()
    entry1.action = MagicMock()
    entry1.action.__str__ = lambda self: "AuditLogAction.ban"
    entry1.target = target
    entry1.user = user
    entry1.reason = "Spam"
    entry1.created_at = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    entry1.before = None
    entry1.after = None
    
    mock_guild.audit_logs = MagicMock(return_value=_make_async_iterator([entry1]))
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert len(result["audit_log_entries"]) == 1
    assert result["audit_log_entries"][0]["action_type"] == "AuditLogAction.ban"
    assert result["audit_log_entries"][0]["user"] == "AdminUser"
    assert result["audit_log_entries"][0]["target"] == "TestUser"
    assert result["audit_log_entries"][0]["reason"] == "Spam"


@pytest.mark.asyncio
async def test_audit_log_with_changes(mock_guild, empty_state):
    # Arrange
    agent = AuditLogInvestigationAgent()
    
    target = MagicMock()
    target.name = "TestChannel"
    
    user = MagicMock()
    user.display_name = "Moderator"
    
    entry = MagicMock()
    entry.action = MagicMock()
    entry.action.__str__ = lambda self: "AuditLogAction.channel_update"
    entry.target = target
    entry.user = user
    entry.reason = None
    entry.created_at = datetime.datetime(2024, 2, 1, tzinfo=datetime.timezone.utc)
    entry.before = MagicMock()
    entry.before.__str__ = lambda self: "old_name"
    entry.after = MagicMock()
    entry.after.__str__ = lambda self: "new_name"
    
    mock_guild.audit_logs = MagicMock(return_value=_make_async_iterator([entry]))
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["audit_log_entries"][0]["changes"] is not None
    assert len(result["audit_log_entries"][0]["changes"]) == 2


@pytest.mark.asyncio
async def test_audit_log_custom_limit(mock_guild, empty_state):
    # Arrange
    agent = AuditLogInvestigationAgent()
    
    target = MagicMock()
    target.name = "TestUser"
    
    user = MagicMock()
    user.display_name = "Admin"
    
    entries = []
    for i in range(5):
        entry = MagicMock()
        entry.action = MagicMock()
        entry.action.__str__ = lambda self: "AuditLogAction.kick"
        entry.target = target
        entry.user = user
        entry.reason = f"Reason {i}"
        entry.created_at = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
        entry.before = None
        entry.after = None
        entries.append(entry)
    
    mock_guild.audit_logs = MagicMock(return_value=_make_async_iterator(entries))
    
    state: AgentState = {**empty_state, "request": "5"}
    
    # Act
    result = await agent.investigate(state, mock_guild)
    
    # Assert
    assert len(result["audit_log_entries"]) == 5


@pytest.mark.asyncio
async def test_audit_log_no_target(mock_guild, empty_state):
    # Arrange
    agent = AuditLogInvestigationAgent()
    
    user = MagicMock()
    user.display_name = "System"
    
    entry = MagicMock()
    entry.action = MagicMock()
    entry.action.__str__ = lambda self: "AuditLogAction.guild_update"
    entry.target = None
    entry.user = user
    entry.reason = None
    entry.created_at = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    entry.before = None
    entry.after = None
    
    mock_guild.audit_logs = MagicMock(return_value=_make_async_iterator([entry]))
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["audit_log_entries"][0]["target"] is None


@pytest.mark.asyncio
async def test_audit_log_agent_name():
    # Arrange & Act
    agent = AuditLogInvestigationAgent()
    
    # Assert
    assert agent.name == "audit_log_investigation"
