"""Tests for MessageExecutionAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock

import discord
from agents.execution.message import MessageExecutionAgent
from graph.state import AgentState


@pytest.fixture
def approved_state():
    return {"approved": True, "todos": [], "user_permissions": {}}


@pytest.mark.asyncio
async def test_send_message(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "send", "params": {"channel_id": 4001, "content": "Hello!"}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "general"
    mock_text_channel.send = AsyncMock(return_value=MagicMock(id=10001))
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Sent message" in result["details"]


@pytest.mark.asyncio
async def test_send_message_missing_channel(mock_guild, approved_state):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "send", "params": {"content": "Hello!"}}]
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "Missing" in result["details"]


@pytest.mark.asyncio
async def test_delete_message(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "delete", "params": {"message_id": 10001}}]
    message = MagicMock()
    message.id = 10001
    message.delete = AsyncMock()
    mock_text_channel.fetch_message = AsyncMock(return_value=message)
    mock_guild.text_channels = [mock_text_channel]
    mock_guild.threads = []
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Deleted" in result["details"]


@pytest.mark.asyncio
async def test_pin_message(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "pin", "params": {"channel_id": 4001, "message_id": 10001}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "general"
    message = MagicMock()
    message.id = 10001
    message.pin = AsyncMock()
    mock_text_channel.fetch_message = AsyncMock(return_value=message)
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Pinned" in result["details"]


@pytest.mark.asyncio
async def test_unpin_message(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "unpin", "params": {"channel_id": 4001, "message_id": 10001}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "general"
    message = MagicMock()
    message.id = 10001
    message.unpin = AsyncMock()
    mock_text_channel.fetch_message = AsyncMock(return_value=message)
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Unpinned" in result["details"]


@pytest.mark.asyncio
async def test_add_reaction(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "add_reaction", "params": {"channel_id": 4001, "message_id": 10001, "emoji": "👍"}}]
    mock_text_channel.id = 4001
    message = MagicMock()
    message.id = 10001
    message.add_reaction = AsyncMock()
    mock_text_channel.fetch_message = AsyncMock(return_value=message)
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "reaction" in result["details"].lower()


@pytest.mark.asyncio
async def test_clear_reactions(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "clear_reactions", "params": {"channel_id": 4001, "message_id": 10001}}]
    mock_text_channel.id = 4001
    message = MagicMock()
    message.id = 10001
    message.clear_reactions = AsyncMock()
    mock_text_channel.fetch_message = AsyncMock(return_value=message)
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Cleared" in result["details"]


@pytest.mark.asyncio
async def test_edit_message(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "edit", "params": {"message_id": 10001, "content": "Updated!"}}]
    message = MagicMock()
    message.id = 10001
    message.edit = AsyncMock()
    mock_text_channel.fetch_message = AsyncMock(return_value=message)
    mock_guild.text_channels = [mock_text_channel]
    mock_guild.threads = []
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is True
    assert "Edited" in result["details"]


@pytest.mark.asyncio
async def test_forbidden_error(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "send", "params": {"channel_id": 4001, "content": "Hello!"}}]
    mock_text_channel.send = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "No permission"))
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    
    # Act
    result = await agent.execute(approved_state, mock_guild)
    
    # Assert
    assert result["success"] is False
    assert "No permission" in result["details"]


def test_message_agent_name():
    agent = MessageExecutionAgent()
    assert agent.name == "message_execution"


def test_action_permissions_defined():
    agent = MessageExecutionAgent()
    assert "send" in agent.ACTION_PERMISSIONS
    assert "delete" in agent.ACTION_PERMISSIONS
    assert "send_messages" in agent.ACTION_PERMISSIONS["send"]


# --- Reply ---


@pytest.mark.asyncio
async def test_send_reply(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "send", "params": {"channel_id": 4001, "content": "Reply!", "message_id": 10001}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "general"
    ref_message = MagicMock()
    ref_message.id = 10001
    mock_text_channel.fetch_message = AsyncMock(return_value=ref_message)
    mock_text_channel.send = AsyncMock(return_value=MagicMock(id=20001))
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    mock_text_channel.send.assert_called_once()
    call_kwargs = mock_text_channel.send.call_args[1]
    assert call_kwargs["reference"] is ref_message


@pytest.mark.asyncio
async def test_send_reply_message_not_found(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "send", "params": {"channel_id": 4001, "content": "Reply!", "message_id": 99999}}]
    mock_text_channel.id = 4001
    mock_text_channel.fetch_message = AsyncMock(side_effect=discord.NotFound(MagicMock(), "Not Found"))
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False


# --- TTS ---


@pytest.mark.asyncio
async def test_send_tts_message(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "send", "params": {"channel_id": 4001, "content": "Hello!", "tts": True}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "general"
    mock_text_channel.send = AsyncMock(return_value=MagicMock(id=10001))
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    call_kwargs = mock_text_channel.send.call_args[1]
    assert call_kwargs["tts"] is True


# --- Crosspost ---


@pytest.mark.asyncio
async def test_crosspost(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "crosspost", "params": {"channel_id": 4001, "message_id": 10001}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "announcements"
    message = MagicMock()
    message.id = 10001
    message.crosspost = AsyncMock()
    mock_text_channel.fetch_message = AsyncMock(return_value=message)
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    assert "Crossposted" in result["details"]
    message.crosspost.assert_awaited_once()


@pytest.mark.asyncio
async def test_crosspost_channel_not_found(mock_guild, approved_state):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "crosspost", "params": {"channel_id": 99999, "message_id": 10001}}]
    mock_guild.get_channel = MagicMock(return_value=None)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False


@pytest.mark.asyncio
async def test_crosspost_message_not_found(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "crosspost", "params": {"channel_id": 4001, "message_id": 99999}}]
    mock_text_channel.id = 4001
    mock_text_channel.fetch_message = AsyncMock(side_effect=discord.NotFound(MagicMock(), "Not Found"))
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False


# --- Sticker ---


@pytest.mark.asyncio
async def test_send_with_sticker(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "send", "params": {"channel_id": 4001, "content": "Hello!", "stickers": [5001]}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "general"
    sticker = MagicMock()
    sticker.id = 5001
    mock_text_channel.send = AsyncMock(return_value=MagicMock(id=10001))
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)
    mock_guild.get_sticker = MagicMock(return_value=sticker)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    call_kwargs = mock_text_channel.send.call_args[1]
    assert call_kwargs["stickers"] == [sticker]


@pytest.mark.asyncio
async def test_send_with_multiple_stickers(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "send", "params": {"channel_id": 4001, "content": "Hello!", "stickers": [5001, 5002]}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "general"
    sticker1 = MagicMock()
    sticker1.id = 5001
    sticker2 = MagicMock()
    sticker2.id = 5002
    mock_text_channel.send = AsyncMock(return_value=MagicMock(id=10001))
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)

    def get_sticker_side_effect(sid):
        return {5001: sticker1, 5002: sticker2}.get(sid)

    mock_guild.get_sticker = MagicMock(side_effect=get_sticker_side_effect)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    call_kwargs = mock_text_channel.send.call_args[1]
    assert call_kwargs["stickers"] == [sticker1, sticker2]


# --- Suppress Embeds ---


@pytest.mark.asyncio
async def test_suppress_embeds(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "suppress_embeds", "params": {"channel_id": 4001, "message_id": 10001}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "general"
    message = MagicMock()
    message.id = 10001
    message.edit = AsyncMock()
    mock_text_channel.fetch_message = AsyncMock(return_value=message)
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    message.edit.assert_awaited_once_with(suppress=True)


@pytest.mark.asyncio
async def test_unsuppress_embeds(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "suppress_embeds", "params": {"channel_id": 4001, "message_id": 10001, "suppress": False}}]
    mock_text_channel.id = 4001
    mock_text_channel.name = "general"
    message = MagicMock()
    message.id = 10001
    message.edit = AsyncMock()
    mock_text_channel.fetch_message = AsyncMock(return_value=message)
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is True
    message.edit.assert_awaited_once_with(suppress=False)


@pytest.mark.asyncio
async def test_suppress_embeds_message_not_found(mock_guild, approved_state, mock_text_channel):
    # Arrange
    agent = MessageExecutionAgent()
    approved_state["todos"] = [{"agent": "message_execution", "action": "suppress_embeds", "params": {"channel_id": 4001, "message_id": 99999}}]
    mock_text_channel.id = 4001
    mock_text_channel.fetch_message = AsyncMock(side_effect=discord.NotFound(MagicMock(), "Not Found"))
    mock_guild.get_channel = MagicMock(return_value=mock_text_channel)

    # Act
    result = await agent.execute(approved_state, mock_guild)

    # Assert
    assert result["success"] is False
