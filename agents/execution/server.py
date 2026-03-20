import discord

from i18n import t

from agents.base import MultiActionExecutionAgent
from graph.state import AgentState


class ServerExecutionAgent(MultiActionExecutionAgent):
    """サーバー全体の設定変更を行うエージェント。"""

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "edit_name": ["manage_guild"],
        "edit_description": ["manage_guild"],
        "edit_verification_level": ["manage_guild"],
        "edit_system_channel": ["manage_guild"],
        "edit_rules_channel": ["manage_guild"],
        "edit_banner": ["manage_guild"],
        "edit_icon": ["manage_guild"],
        "edit_public_updates_channel": ["manage_guild"],
        "edit_afk": ["manage_guild"],
        "edit_content_filter": ["manage_guild"],
        "edit_notification_level": ["manage_guild"],
        "edit_safety_alerts_channel": ["manage_guild"],
    }

    @property
    def name(self) -> str:
        return "server_execution"

    async def _dispatch(self, action: str, params: dict, guild: discord.Guild) -> dict:
        handlers = {
            "edit_name": self._edit_name,
            "edit_description": self._edit_description,
            "edit_verification_level": self._edit_verification_level,
            "edit_system_channel": self._edit_system_channel,
            "edit_rules_channel": self._edit_rules_channel,
            "edit_banner": self._edit_banner,
            "edit_icon": self._edit_icon,
            "edit_public_updates_channel": self._edit_public_updates_channel,
            "edit_afk": self._edit_afk,
            "edit_content_filter": self._edit_content_filter,
            "edit_notification_level": self._edit_notification_level,
            "edit_safety_alerts_channel": self._edit_safety_alerts_channel,
        }
        handler = handlers.get(action)
        if not handler:
            return {"success": False, "action": action, "details": t("err.unknown_action", locale=self._locale, action=action)}
        return await handler(params, guild)

    async def _edit_name(self, params: dict, guild: discord.Guild) -> dict:
        """サーバー名を変更する。"""
        name = params.get("name")
        if not name:
            return {"success": False, "action": "edit_name", "details": t("exec.missing_param", locale=self._locale, param="name")}
        try:
            await guild.edit(name=name)
            return {"success": True, "action": "edit_name", "details": t("exec.server.name_changed", locale=self._locale, name=name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit_name", "details": str(e)}

    async def _edit_description(self, params: dict, guild: discord.Guild) -> dict:
        """サーバー説明文を変更する。"""
        description = params.get("description")
        if description is None:
            return {"success": False, "action": "edit_description", "details": t("exec.missing_param", locale=self._locale, param="description")}
        try:
            await guild.edit(description=description)
            return {"success": True, "action": "edit_description", "details": t("exec.server.description_updated", locale=self._locale)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit_description", "details": str(e)}

    async def _edit_verification_level(self, params: dict, guild: discord.Guild) -> dict:
        """サーバーの認証レベルを変更する。"""
        level_name = params.get("level")
        if not level_name:
            return {"success": False, "action": "edit_verification_level", "details": t("exec.missing_param", locale=self._locale, param="level")}
        level_map = {
            "none": discord.VerificationLevel.none,
            "low": discord.VerificationLevel.low,
            "medium": discord.VerificationLevel.medium,
            "high": discord.VerificationLevel.high,
            "highest": discord.VerificationLevel.highest,
        }
        level = level_map.get(level_name.lower())
        if not level:
            return {"success": False, "action": "edit_verification_level", "details": t("exec.server.invalid_level", locale=self._locale, level=level_name)}
        try:
            await guild.edit(verification_level=level)
            return {"success": True, "action": "edit_verification_level", "details": t("exec.server.verification_level", locale=self._locale, level=level_name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit_verification_level", "details": str(e)}

    async def _edit_system_channel(self, params: dict, guild: discord.Guild) -> dict:
        """システムチャンネルを設定する。"""
        channel_id = params.get("channel_id")
        if not channel_id:
            return {"success": False, "action": "edit_system_channel", "details": t("exec.missing_param", locale=self._locale, param="channel_id")}
        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "edit_system_channel", "details": t("not_found.channel", locale=self._locale, id=channel_id)}
        try:
            await guild.edit(system_channel=channel)
            return {"success": True, "action": "edit_system_channel", "details": t("exec.server.system_channel", locale=self._locale, channel=channel.name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit_system_channel", "details": str(e)}

    async def _edit_rules_channel(self, params: dict, guild: discord.Guild) -> dict:
        """ルールチャンネルを設定する。"""
        channel_id = params.get("channel_id")
        if not channel_id:
            return {"success": False, "action": "edit_rules_channel", "details": t("exec.missing_param", locale=self._locale, param="channel_id")}
        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "edit_rules_channel", "details": t("not_found.channel", locale=self._locale, id=channel_id)}
        try:
            await guild.edit(rules_channel=channel)
            return {"success": True, "action": "edit_rules_channel", "details": t("exec.server.rules_channel", locale=self._locale, channel=channel.name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit_rules_channel", "details": str(e)}

    async def _edit_banner(self, params: dict, guild: discord.Guild) -> dict:
        """サーバーバナー画像を設定する。"""
        banner = params.get("banner")
        if not banner:
            return {"success": False, "action": "edit_banner", "details": t("exec.server.missing_banner", locale=self._locale)}
        try:
            await guild.edit(banner=banner)
            return {"success": True, "action": "edit_banner", "details": t("exec.server.banner_updated", locale=self._locale)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit_banner", "details": str(e)}

    async def _edit_icon(self, params: dict, guild: discord.Guild) -> dict:
        """サーバーアイコンを変更する。"""
        icon = params.get("icon")
        if not icon:
            return {"success": False, "action": "edit_icon", "details": t("exec.missing_param", locale=self._locale, param="icon")}
        try:
            await guild.edit(icon=icon)
            return {"success": True, "action": "edit_icon", "details": t("exec.server.icon_updated", locale=self._locale)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit_icon", "details": str(e)}

    async def _edit_public_updates_channel(self, params: dict, guild: discord.Guild) -> dict:
        """公開アップデートチャンネルを設定する。"""
        channel_id = params.get("channel_id")
        if not channel_id:
            return {"success": False, "action": "edit_public_updates_channel", "details": t("exec.missing_param", locale=self._locale, param="channel_id")}
        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "edit_public_updates_channel", "details": t("not_found.channel", locale=self._locale, id=channel_id)}
        try:
            await guild.edit(public_updates_channel=channel)
            return {"success": True, "action": "edit_public_updates_channel", "details": t("exec.server.public_updates_channel", locale=self._locale, channel=channel.name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit_public_updates_channel", "details": str(e)}

    async def _edit_afk(self, params: dict, guild: discord.Guild) -> dict:
        """AFKチャンネルとタイムアウトを設定する。"""
        channel_id = params.get("channel_id")
        if not channel_id:
            return {"success": False, "action": "edit_afk", "details": t("exec.missing_param", locale=self._locale, param="channel_id")}
        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "edit_afk", "details": t("not_found.channel", locale=self._locale, id=channel_id)}
        timeout = params.get("timeout", 300)
        try:
            await guild.edit(afk_channel=channel, afk_timeout=timeout)
            return {"success": True, "action": "edit_afk", "details": t("exec.server.afk_channel", locale=self._locale, channel=channel.name, timeout=timeout)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit_afk", "details": str(e)}

    async def _edit_content_filter(self, params: dict, guild: discord.Guild) -> dict:
        """明示的コンテンツフィルターレベルを変更する。"""
        level_name = params.get("level")
        if not level_name:
            return {"success": False, "action": "edit_content_filter", "details": t("exec.missing_param", locale=self._locale, param="level")}
        level_map = {
            "disabled": discord.ContentFilter.disabled,
            "no_role": discord.ContentFilter.no_role,
            "members_without_roles": discord.ContentFilter.try_value,
            "all_members": discord.ContentFilter.all_members,
        }
        level = level_map.get(level_name.lower())
        if not level:
            return {"success": False, "action": "edit_content_filter", "details": t("exec.server.invalid_content_filter", locale=self._locale, level=level_name)}
        try:
            await guild.edit(explicit_content_filter=level)
            return {"success": True, "action": "edit_content_filter", "details": t("exec.server.content_filter", locale=self._locale, level=level_name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit_content_filter", "details": str(e)}

    async def _edit_notification_level(self, params: dict, guild: discord.Guild) -> dict:
        """デフォルト通知レベルを変更する。"""
        level_name = params.get("level")
        if not level_name:
            return {"success": False, "action": "edit_notification_level", "details": t("exec.missing_param", locale=self._locale, param="level")}
        level_map = {
            "all_messages": discord.NotificationLevel.all_messages,
            "only_mentions": discord.NotificationLevel.only_mentions,
        }
        level = level_map.get(level_name.lower())
        if not level:
            return {"success": False, "action": "edit_notification_level", "details": t("exec.server.invalid_notification_level", locale=self._locale, level=level_name)}
        try:
            await guild.edit(default_notifications=level)
            return {"success": True, "action": "edit_notification_level", "details": t("exec.server.notification_level", locale=self._locale, level=level_name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit_notification_level", "details": str(e)}

    async def _edit_safety_alerts_channel(self, params: dict, guild: discord.Guild) -> dict:
        """セーフティアラートチャンネルを設定する。"""
        channel_id = params.get("channel_id")
        if not channel_id:
            return {"success": False, "action": "edit_safety_alerts_channel", "details": t("exec.missing_param", locale=self._locale, param="channel_id")}
        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "edit_safety_alerts_channel", "details": t("not_found.channel", locale=self._locale, id=channel_id)}
        try:
            await guild.edit(safety_alerts_channel=channel)
            return {"success": True, "action": "edit_safety_alerts_channel", "details": t("exec.server.safety_alerts_channel", locale=self._locale, channel=channel.name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit_safety_alerts_channel", "details": str(e)}
