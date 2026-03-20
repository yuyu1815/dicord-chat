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
