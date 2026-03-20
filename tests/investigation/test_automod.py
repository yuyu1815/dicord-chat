"""Tests for AutoModInvestigationAgent using AAA pattern."""
import pytest
from unittest.mock import MagicMock, AsyncMock

from agents.investigation.automod import AutoModInvestigationAgent
from graph.state import AgentState


@pytest.mark.asyncio
async def test_automod_rule_list(mock_guild, empty_state):
    # Arrange
    agent = AutoModInvestigationAgent()
    
    role1 = MagicMock()
    role1.name = "Admin"
    role2 = MagicMock()
    role2.name = "Moderator"
    
    channel1 = MagicMock()
    channel1.name = "general"
    channel2 = MagicMock()
    channel2.name = "off-topic"
    
    trigger = MagicMock()
    trigger.type = MagicMock()
    trigger.type.__str__ = lambda self: "AutoModRuleTriggerType.keyword"
    trigger.keyword_filter = ["spam", "scam"]
    trigger.regex_patterns = None
    trigger.presets = None
    trigger.allow_list = None
    trigger.mention_limit = None
    
    action1 = MagicMock()
    action1.type = MagicMock()
    action1.type.__str__ = lambda self: "AutoModActionType.block_message"
    action1.channel_id = None
    action1.duration = None
    action1.custom_message = None
    
    action2 = MagicMock()
    action2.type = MagicMock()
    action2.type.__str__ = lambda self: "AutoModActionType.timeout"
    action2.channel_id = None
    action2.duration = 60
    action2.custom_message = "You have been timed out"
    
    rule = MagicMock()
    rule.id = 1001
    rule.name = "Anti-spam Rule"
    rule.enabled = True
    rule.event_type = MagicMock()
    rule.event_type.__str__ = lambda self: "AutoModRuleEventType.message_send"
    rule.trigger = trigger
    rule.actions = [action1, action2]
    rule.exempt_roles = [role1, role2]
    rule.exempt_channels = [channel1, channel2]
    
    mock_guild.fetch_automod_rules = AsyncMock(return_value=[rule])
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert len(result["auto_moderation_rules"]) == 1
    assert result["auto_moderation_rules"][0]["name"] == "Anti-spam Rule"
    assert result["auto_moderation_rules"][0]["enabled"] is True
    assert result["auto_moderation_rules"][0]["trigger"]["type"] == "AutoModRuleTriggerType.keyword"
    assert result["auto_moderation_rules"][0]["trigger"]["keyword_filter"] == ["spam", "scam"]


@pytest.mark.asyncio
async def test_automod_multiple_rules(mock_guild, empty_state):
    # Arrange
    agent = AutoModInvestigationAgent()
    
    trigger1 = MagicMock()
    trigger1.type = MagicMock()
    trigger1.type.__str__ = lambda self: "AutoModRuleTriggerType.keyword"
    trigger1.keyword_filter = ["bad"]
    trigger1.regex_patterns = None
    trigger1.presets = None
    trigger1.allow_list = None
    trigger1.mention_limit = None
    
    trigger2 = MagicMock()
    trigger2.type = MagicMock()
    trigger2.type.__str__ = lambda self: "AutoModRuleTriggerType.spam"
    trigger2.keyword_filter = None
    trigger2.regex_patterns = None
    trigger2.presets = None
    trigger2.allow_list = None
    trigger2.mention_limit = None
    
    rule1 = MagicMock()
    rule1.id = 1001
    rule1.name = "Keyword Block"
    rule1.enabled = True
    rule1.event_type = MagicMock()
    rule1.event_type.__str__ = lambda self: "AutoModRuleEventType.message_send"
    rule1.trigger = trigger1
    rule1.actions = []
    rule1.exempt_roles = []
    rule1.exempt_channels = []
    
    rule2 = MagicMock()
    rule2.id = 1002
    rule2.name = "Spam Filter"
    rule2.enabled = False
    rule2.event_type = MagicMock()
    rule2.event_type.__str__ = lambda self: "AutoModRuleEventType.message_send"
    rule2.trigger = trigger2
    rule2.actions = []
    rule2.exempt_roles = []
    rule2.exempt_channels = []
    
    mock_guild.fetch_automod_rules = AsyncMock(return_value=[rule1, rule2])
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["auto_moderation_rules"][0]["name"] == "Keyword Block"
    assert result["auto_moderation_rules"][1]["name"] == "Spam Filter"


@pytest.mark.asyncio
async def test_automod_empty_list(mock_guild, empty_state):
    # Arrange
    agent = AutoModInvestigationAgent()
    mock_guild.fetch_automod_rules = AsyncMock(return_value=[])
    
    # Act
    result = await agent.investigate(empty_state, mock_guild)
    
    # Assert
    assert result["auto_moderation_rules"] == []
    assert result["total_count"] == 0


@pytest.mark.asyncio
async def test_automod_agent_name():
    # Arrange & Act
    agent = AutoModInvestigationAgent()
    
    # Assert
    assert agent.name == "automod_investigation"
