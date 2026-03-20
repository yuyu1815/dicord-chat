"""Tests for ServerExecutionAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock
import discord

from agents.execution.server import ServerExecutionAgent
from graph.state import AgentState


@pytest.fixture
def approved_state():
    return {"approved": True, "todos": [], "user_permissions": {}}


@pytest.mark.asyncio
async def test_edit_server_name(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_name", "params": {"name": "New Server Name"}}]
    mock_guild.edit = AsyncMock()
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "edit_name" in result["action"]
    mock_guild.edit.assert_called_once_with(name="New Server Name")


@pytest.mark.asyncio
async def test_edit_server_name_missing_param(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_name", "params": {}}]
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "Missing" in result["details"]


@pytest.mark.asyncio
async def test_edit_server_description(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_description", "params": {"description": "A new description"}}]
    mock_guild.edit = AsyncMock()
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    mock_guild.edit.assert_called_once_with(description="A new description")


@pytest.mark.asyncio
async def test_edit_verification_level(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_verification_level", "params": {"level": "high"}}]
    mock_guild.edit = AsyncMock()
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "high" in result["details"]


@pytest.mark.asyncio
async def test_edit_verification_level_invalid(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_verification_level", "params": {"level": "invalid"}}]
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "Invalid level" in result["details"]


@pytest.mark.asyncio
async def test_edit_system_channel(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_system_channel", "params": {"channel_id": 4001}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "system-messages"
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    mock_guild.edit = AsyncMock()
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    mock_guild.edit.assert_called_once()


@pytest.mark.asyncio
async def test_edit_system_channel_not_found(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_system_channel", "params": {"channel_id": 99999}}]
    mock_guild.get_channel = MagicMock(return_value=None)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "not found" in result["details"]


@pytest.mark.asyncio
async def test_edit_rules_channel(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_rules_channel", "params": {"channel_id": 4001}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "rules"
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    mock_guild.edit = AsyncMock()
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True


@pytest.mark.asyncio
async def test_multiple_actions(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [
        {"agent": "server_execution", "action": "edit_name", "params": {"name": "New Name"}},
        {"agent": "server_execution", "action": "edit_description", "params": {"description": "New Desc"}},
    ]
    mock_guild.edit = AsyncMock()
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "edit_name" in result["action"]
    assert "edit_description" in result["action"]


@pytest.mark.asyncio
async def test_no_matching_todos(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "other_agent", "action": "edit_name", "params": {}}]
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "No matching action" in result["details"]


@pytest.mark.asyncio
async def test_forbidden_error(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_name", "params": {"name": "New"}}]
    mock_guild.edit = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "Missing permissions"))
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "Missing permissions" in result["details"]


def test_server_agent_name():
    # Arrange & Act
    agent = ServerExecutionAgent()
    
    # Assert
    assert agent.name == "server_execution"


def test_action_permissions_defined():
    # Arrange & Act
    agent = ServerExecutionAgent()

    # Assert
    assert "edit_name" in agent.ACTION_PERMISSIONS
    assert "edit_description" in agent.ACTION_PERMISSIONS
    assert "manage_guild" in agent.ACTION_PERMISSIONS["edit_name"]


# --- #11 Edit Icon ---


@pytest.mark.asyncio
async def test_edit_icon(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    icon_data = b"\x89PNG\r\n\x1a\nfake icon bytes"
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_icon", "params": {"icon": icon_data}}]
    mock_guild.edit = AsyncMock()

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    mock_guild.edit.assert_called_once_with(icon=icon_data)


@pytest.mark.asyncio
async def test_edit_icon_missing_param(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_icon", "params": {}}]

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False


# --- #12 Edit Public Updates Channel ---


@pytest.mark.asyncio
async def test_edit_public_updates_channel(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_public_updates_channel", "params": {"channel_id": 4001}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "public-updates"
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    mock_guild.edit = AsyncMock()

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    mock_guild.edit.assert_called_once_with(public_updates_channel=mock_text_channel)


@pytest.mark.asyncio
async def test_edit_public_updates_channel_not_found(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_public_updates_channel", "params": {"channel_id": 99999}}]
    mock_guild.get_channel = MagicMock(return_value=None)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False
    assert "not found" in result["details"]


# --- #13 Edit AFK Channel + Timeout ---


@pytest.mark.asyncio
async def test_edit_afk_channel(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_afk", "params": {"channel_id": 4001}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "afk-channel"
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    mock_guild.edit = AsyncMock()

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    mock_guild.edit.assert_called_once_with(afk_channel=mock_text_channel, afk_timeout=300)


@pytest.mark.asyncio
async def test_edit_afk_channel_with_custom_timeout(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_afk", "params": {"channel_id": 4001, "timeout": 600}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "afk-channel"
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    mock_guild.edit = AsyncMock()

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    mock_guild.edit.assert_called_once_with(afk_channel=mock_text_channel, afk_timeout=600)


@pytest.mark.asyncio
async def test_edit_afk_channel_not_found(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_afk", "params": {"channel_id": 99999}}]
    mock_guild.get_channel = MagicMock(return_value=None)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False
    assert "not found" in result["details"]


# --- #14 Edit Explicit Content Filter ---


@pytest.mark.asyncio
@pytest.mark.parametrize("level_name,expected", [
    ("disabled", discord.ContentFilter.disabled),
    ("no_role", discord.ContentFilter.no_role),
    ("all_members", discord.ContentFilter.all_members),
])
async def test_edit_content_filter(mock_guild, approved_state, level_name, expected):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_content_filter", "params": {"level": level_name}}]
    mock_guild.edit = AsyncMock()

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    mock_guild.edit.assert_called_once_with(explicit_content_filter=expected)


@pytest.mark.asyncio
async def test_edit_content_filter_invalid_level(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_content_filter", "params": {"level": "invalid_level"}}]

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False
    assert "invalid" in result["details"]


@pytest.mark.asyncio
async def test_edit_content_filter_missing_param(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_content_filter", "params": {}}]

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False


# --- #15 Edit Default Notification Level ---


@pytest.mark.asyncio
@pytest.mark.parametrize("level_name,expected", [
    ("all_messages", discord.NotificationLevel.all_messages),
    ("only_mentions", discord.NotificationLevel.only_mentions),
])
async def test_edit_notification_level(mock_guild, approved_state, level_name, expected):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_notification_level", "params": {"level": level_name}}]
    mock_guild.edit = AsyncMock()

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    mock_guild.edit.assert_called_once_with(default_notifications=expected)


@pytest.mark.asyncio
async def test_edit_notification_level_invalid_level(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_notification_level", "params": {"level": "invalid_level"}}]

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False


@pytest.mark.asyncio
async def test_edit_notification_level_missing_param(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_notification_level", "params": {}}]

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False


# --- #16 Edit Safety Alerts Channel ---


@pytest.mark.asyncio
async def test_edit_safety_alerts_channel(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_safety_alerts_channel", "params": {"channel_id": 4001}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "safety-alerts"
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    mock_guild.edit = AsyncMock()

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    mock_guild.edit.assert_called_once_with(safety_alerts_channel=mock_text_channel)


@pytest.mark.asyncio
async def test_edit_safety_alerts_channel_not_found(mock_guild, approved_state):
    # Arrange
    agent = ServerExecutionAgent()
    approved_state["todos"] = [{"agent": "server_execution", "action": "edit_safety_alerts_channel", "params": {"channel_id": 99999}}]
    mock_guild.get_channel = MagicMock(return_value=None)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False
    assert "not found" in result["details"]
