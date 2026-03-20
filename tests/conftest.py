"""Pytest configuration and fixtures for Discord bot tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock
import datetime

import discord

from agents.ratelimit import _history


@pytest.fixture(autouse=True)
def reset_ratelimit_history():
    """Reset channel name/topic edit rate limit history between tests."""
    _history.clear()
    yield
    _history.clear()


@pytest.fixture
def mock_guild():
    """Create a mock Discord Guild for testing."""
    guild = MagicMock(spec=discord.Guild)
    guild.id = 123456789
    guild.name = "Test Server"
    guild.owner_id = 1001
    guild.member_count = 5
    guild.created_at = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    guild.verification_level = discord.VerificationLevel.medium
    guild.icon = None
    guild.banner = None
    guild.description = "Test server description"
    guild.features = ["COMMUNITY", "NEWS"]
    guild.system_channel = None
    guild.rules_channel = None
    guild.max_members = 100000
    guild.premium_tier = 1
    guild.nsfw_level = discord.NSFWLevel.default
    
    # Collections
    guild.roles = []
    guild.text_channels = []
    guild.voice_channels = []
    guild.stage_channels = []
    guild.threads = []
    guild.channels = []
    guild.emojis = []
    guild.stickers = []
    guild.scheduled_events = []
    
    # Async methods
    guild.fetch_members = AsyncMock(return_value=[])
    guild.fetch_member = AsyncMock(return_value=None)
    guild.get_member = MagicMock(return_value=None)
    guild.invites = AsyncMock(return_value=[])
    guild.fetch_automod_rules = AsyncMock(return_value=[])
    guild.audit_logs = AsyncMock(return_value=[])
    
    return guild


@pytest.fixture
def mock_member():
    """Create a mock Discord Member for testing."""
    member = MagicMock(spec=discord.Member)
    member.id = 2001
    member.name = "TestUser"
    member.display_name = "TestDisplayName"
    member.nick = "TestNick"
    member.display_avatar = MagicMock()
    member.display_avatar.url = "https://example.com/avatar.png"
    member.joined_at = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    member.created_at = datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc)
    member.bot = False
    member.top_role = MagicMock()
    member.top_role.name = "Member"
    member.roles = []
    member.status = discord.Status.online
    member.activities = []
    member.voice = None
    
    return member


@pytest.fixture
def mock_role():
    """Create a mock Discord Role for testing."""
    role = MagicMock(spec=discord.Role)
    role.id = 3001
    role.name = "TestRole"
    role.color = discord.Color.blue()
    role.position = 1
    role.mentionable = True
    role.managed = False
    role.permissions = MagicMock()
    role.permissions.administrator = False
    role.permissions.manage_guild = False
    role.permissions.manage_channels = False
    role.members = []
    
    return role


@pytest.fixture
def mock_text_channel():
    """Create a mock Discord TextChannel for testing."""
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 4001
    channel.name = "test-channel"
    channel.type = discord.ChannelType.text
    channel.category = None
    channel.position = 1
    channel.nsfw = False
    channel.topic = "Test channel topic"
    channel.mentions = []
    channel.overwrites = {}
    
    # Async methods
    channel.history = AsyncMock(return_value=[])
    channel.send = AsyncMock(return_value=MagicMock())
    channel.webhooks = AsyncMock(return_value=[])
    
    return channel


@pytest.fixture
def mock_voice_channel():
    """Create a mock Discord VoiceChannel for testing."""
    channel = MagicMock(spec=discord.VoiceChannel)
    channel.id = 4002
    channel.name = "test-voice"
    channel.type = discord.ChannelType.voice
    channel.category = None
    channel.position = 1
    channel.bitrate = 64000
    channel.user_limit = 10
    channel.nsfw = False
    channel.members = []
    
    return channel


@pytest.fixture
def mock_category():
    """Create a mock Discord CategoryChannel for testing."""
    category = MagicMock(spec=discord.CategoryChannel)
    category.id = 5001
    category.name = "Test Category"
    category.type = discord.ChannelType.category
    category.position = 1
    category.channels = []
    
    return category


@pytest.fixture
def empty_state() -> dict:
    """Return an empty agent state."""
    return {
        "request": "",
        "todos": [],
        "investigation_results": {},
        "approved": False,
        "execution_results": {},
        "final_response": "",
        "error": None,
    }
