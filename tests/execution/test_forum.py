"""Tests for ForumExecutionAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock

import discord
from agents.execution.forum import ForumExecutionAgent
from graph.state import AgentState


@pytest.fixture
def approved_state():
    return {"approved": True, "todos": [], "user_permissions": {}}


@pytest.fixture
def mock_forum_channel():
    channel = MagicMock(spec=discord.ForumChannel)
    channel.id = 5001
    channel.name = "community-forum"
    channel.available_tags = []
    channel.create_thread = AsyncMock()
    channel.create_tag = AsyncMock()
    channel.threads = []
    return channel


@pytest.mark.asyncio
async def test_create_post(mock_guild, approved_state, mock_forum_channel):
    # Arrange
    agent = ForumExecutionAgent()
    approved_state["todos"] = [{"agent": "forum_execution", "action": "create_post", "params": {"forum_channel_id": 5001, "title": "Hello World", "content": "First post!"}}]
    thread = MagicMock()
    thread.id = 6001
    mock_forum_channel.create_thread = AsyncMock(return_value=thread)
    mock_guild.get_channel = MagicMock(return_value=mock_forum_channel)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    assert "Hello World" in result["details"]


@pytest.mark.asyncio
async def test_create_post_missing_forum_id(mock_guild, approved_state):
    # Arrange
    agent = ForumExecutionAgent()
    approved_state["todos"] = [{"agent": "forum_execution", "action": "create_post", "params": {"title": "Hello"}}]

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False
    assert "forum_channel_id" in result["details"]


@pytest.mark.asyncio
async def test_create_post_missing_title(mock_guild, approved_state):
    # Arrange
    agent = ForumExecutionAgent()
    approved_state["todos"] = [{"agent": "forum_execution", "action": "create_post", "params": {"forum_channel_id": 5001}}]

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False
    assert "title" in result["details"]


@pytest.mark.asyncio
async def test_create_post_forum_not_found(mock_guild, approved_state):
    # Arrange
    agent = ForumExecutionAgent()
    approved_state["todos"] = [{"agent": "forum_execution", "action": "create_post", "params": {"forum_channel_id": 99999, "title": "Test"}}]
    mock_guild.get_channel = MagicMock(return_value=None)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False
    assert "not found" in result["details"]


@pytest.mark.asyncio
async def test_create_post_with_tags(mock_guild, approved_state, mock_forum_channel):
    # Arrange
    agent = ForumExecutionAgent()
    tag = MagicMock()
    tag.id = 101
    tag.name = "bug"
    mock_forum_channel.available_tags = [tag]
    approved_state["todos"] = [{"agent": "forum_execution", "action": "create_post", "params": {"forum_channel_id": 5001, "title": "Bug Report", "content": "Something broke", "tags_list": [101]}}]
    thread = MagicMock()
    thread.id = 6002
    mock_forum_channel.create_thread = AsyncMock(return_value=thread)
    mock_guild.get_channel = MagicMock(return_value=mock_forum_channel)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    mock_forum_channel.create_thread.assert_called_once()
    call_kwargs = mock_forum_channel.create_thread.call_args
    assert len(call_kwargs.kwargs.get("applied_tags", [])) == 1


@pytest.mark.asyncio
async def test_create_post_forbidden_error(mock_guild, approved_state, mock_forum_channel):
    # Arrange
    agent = ForumExecutionAgent()
    approved_state["todos"] = [{"agent": "forum_execution", "action": "create_post", "params": {"forum_channel_id": 5001, "title": "Test"}}]
    mock_forum_channel.create_thread = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "No permission"))
    mock_guild.get_channel = MagicMock(return_value=mock_forum_channel)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False


@pytest.mark.asyncio
async def test_delete_post(mock_guild, approved_state, mock_forum_channel):
    # Arrange
    agent = ForumExecutionAgent()
    thread = MagicMock()
    thread.id = 6001
    thread.name = "Old Post"
    thread.owner_id = 1
    thread.starter_message_id = 7001
    thread.delete = AsyncMock()
    mock_forum_channel.threads = [thread]
    mock_guild.channels = [mock_forum_channel]

    approved_state["todos"] = [{"agent": "forum_execution", "action": "delete_post", "params": {"message_id": 6001}}]

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    assert "Old Post" in result["details"]


@pytest.mark.asyncio
async def test_delete_post_not_found(mock_guild, approved_state):
    # Arrange
    agent = ForumExecutionAgent()
    mock_guild.channels = []
    approved_state["todos"] = [{"agent": "forum_execution", "action": "delete_post", "params": {"message_id": 99999}}]

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False
    assert "not find" in result["details"]


@pytest.mark.asyncio
async def test_create_tag(mock_guild, approved_state, mock_forum_channel):
    # Arrange
    agent = ForumExecutionAgent()
    tag = MagicMock()
    tag.id = 201
    tag.name = "feature"
    mock_forum_channel.create_tag = AsyncMock(return_value=tag)
    mock_guild.get_channel = MagicMock(return_value=mock_forum_channel)

    approved_state["todos"] = [{"agent": "forum_execution", "action": "create_tag", "params": {"forum_channel_id": 5001, "name": "feature"}}]

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    assert "feature" in result["details"]


@pytest.mark.asyncio
async def test_edit_tag(mock_guild, approved_state, mock_forum_channel):
    # Arrange
    agent = ForumExecutionAgent()
    tag = MagicMock()
    tag.id = 101
    tag.name = "bug"
    tag.edit = AsyncMock()
    mock_forum_channel.available_tags = [tag]
    mock_guild.get_channel = MagicMock(return_value=mock_forum_channel)

    approved_state["todos"] = [{"agent": "forum_execution", "action": "edit_tag", "params": {"forum_channel_id": 5001, "tag_id": 101, "name": "critical-bug"}}]

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    tag.edit.assert_called_once_with(name="critical-bug")


@pytest.mark.asyncio
async def test_edit_tag_not_found(mock_guild, approved_state, mock_forum_channel):
    # Arrange
    agent = ForumExecutionAgent()
    mock_forum_channel.available_tags = []
    mock_guild.get_channel = MagicMock(return_value=mock_forum_channel)

    approved_state["todos"] = [{"agent": "forum_execution", "action": "edit_tag", "params": {"forum_channel_id": 5001, "tag_id": 999}}]

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False
    assert "not found" in result["details"]


@pytest.mark.asyncio
async def test_delete_tag(mock_guild, approved_state, mock_forum_channel):
    # Arrange
    agent = ForumExecutionAgent()
    tag = MagicMock()
    tag.id = 101
    tag.name = "obsolete"
    tag.delete = AsyncMock()
    mock_forum_channel.available_tags = [tag]
    mock_guild.get_channel = MagicMock(return_value=mock_forum_channel)

    approved_state["todos"] = [{"agent": "forum_execution", "action": "delete_tag", "params": {"forum_channel_id": 5001, "tag_id": 101}}]

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    assert "obsolete" in result["details"]


@pytest.mark.asyncio
async def test_no_matching_todos(mock_guild, approved_state):
    # Arrange
    agent = ForumExecutionAgent()
    approved_state["todos"] = [{"agent": "other_agent", "action": "something"}]

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False
    assert "No matching" in result["details"]


def test_forum_agent_name():
    agent = ForumExecutionAgent()
    assert agent.name == "forum_execution"


def test_action_permissions_defined():
    agent = ForumExecutionAgent()
    assert "create_post" in agent.ACTION_PERMISSIONS
    assert "send_messages" in agent.ACTION_PERMISSIONS["create_post"]
    assert "delete_post" in agent.ACTION_PERMISSIONS
    assert "manage_threads" in agent.ACTION_PERMISSIONS["delete_post"]


@pytest.mark.asyncio
async def test_create_forum_channel(mock_guild, approved_state):
    # Arrange
    agent = ForumExecutionAgent()
    channel = MagicMock(spec=discord.ForumChannel)
    channel.name = "new-forum"
    channel.id = 7001
    mock_guild.create_forum_channel = AsyncMock(return_value=channel)
    approved_state["todos"] = [{"agent": "forum_execution", "action": "create_channel", "params": {"name": "new-forum"}}]

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    assert "Created forum channel" in result["details"]


@pytest.mark.asyncio
async def test_create_forum_channel_with_category(mock_guild, approved_state, mock_category):
    # Arrange
    agent = ForumExecutionAgent()
    channel = MagicMock(spec=discord.ForumChannel)
    channel.name = "cat-forum"
    channel.id = 7002
    mock_guild.create_forum_channel = AsyncMock(return_value=channel)
    mock_guild.get_channel = MagicMock(return_value=mock_category)
    approved_state["todos"] = [{"agent": "forum_execution", "action": "create_channel", "params": {"name": "cat-forum", "category_id": 5001}}]

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    mock_guild.create_forum_channel.assert_called_once()
    call_kwargs = mock_guild.create_forum_channel.call_args
    assert call_kwargs.kwargs["category"] == mock_category


@pytest.mark.asyncio
async def test_create_forum_channel_with_topic(mock_guild, approved_state):
    # Arrange
    agent = ForumExecutionAgent()
    channel = MagicMock(spec=discord.ForumChannel)
    channel.name = "topic-forum"
    channel.id = 7003
    mock_guild.create_forum_channel = AsyncMock(return_value=channel)
    approved_state["todos"] = [{"agent": "forum_execution", "action": "create_channel", "params": {"name": "topic-forum", "topic": "Discuss things here"}}]

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    mock_guild.create_forum_channel.assert_called_once()
    call_kwargs = mock_guild.create_forum_channel.call_args
    assert call_kwargs.kwargs["topic"] == "Discuss things here"


@pytest.mark.asyncio
async def test_create_forum_channel_missing_name(mock_guild, approved_state):
    # Arrange
    agent = ForumExecutionAgent()
    approved_state["todos"] = [{"agent": "forum_execution", "action": "create_channel", "params": {}}]

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False


@pytest.mark.asyncio
async def test_edit_forum_channel(mock_guild, approved_state):
    # Arrange
    agent = ForumExecutionAgent()
    channel = MagicMock(spec=discord.ForumChannel)
    channel.name = "old-name"
    channel.edit = AsyncMock()
    mock_guild.get_channel = MagicMock(return_value=channel)
    approved_state["todos"] = [{"agent": "forum_execution", "action": "edit_channel", "params": {"channel_id": 7001, "name": "new-name"}}]

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    channel.edit.assert_called_once()


@pytest.mark.asyncio
async def test_edit_forum_channel_not_found(mock_guild, approved_state):
    # Arrange
    agent = ForumExecutionAgent()
    mock_guild.get_channel = MagicMock(return_value=None)
    approved_state["todos"] = [{"agent": "forum_execution", "action": "edit_channel", "params": {"channel_id": 99999}}]

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False
    assert "not found" in result["details"]


@pytest.mark.asyncio
async def test_delete_forum_channel(mock_guild, approved_state):
    # Arrange
    agent = ForumExecutionAgent()
    channel = MagicMock(spec=discord.ForumChannel)
    channel.name = "doomed-forum"
    channel.delete = AsyncMock()
    mock_guild.get_channel = MagicMock(return_value=channel)
    approved_state["todos"] = [{"agent": "forum_execution", "action": "delete_channel", "params": {"channel_id": 7001}}]

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    channel.delete.assert_called_once()


@pytest.mark.asyncio
async def test_delete_forum_channel_not_found(mock_guild, approved_state):
    # Arrange
    agent = ForumExecutionAgent()
    mock_guild.get_channel = MagicMock(return_value=None)
    approved_state["todos"] = [{"agent": "forum_execution", "action": "delete_channel", "params": {"channel_id": 99999}}]

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False
    assert "not found" in result["details"]
