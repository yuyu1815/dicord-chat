import discord

from agents.base import MultiActionExecutionAgent
from graph.state import AgentState
from i18n import t


class VoiceChannelExecutionAgent(MultiActionExecutionAgent):
    """ボイスチャンネルの操作（メンバー移動・ミュート・切断・チャンネル編集）を行うエージェント。"""

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "move_user": ["move_members"],
        "mute": ["mute_members"],
        "unmute": ["mute_members"],
        "deafen": ["deafen_members"],
        "undeafen": ["deafen_members"],
        "disconnect": ["move_members"],
        "edit_channel": ["manage_channels"],
    }

    @property
    def name(self) -> str:
        return "vc_execution"

    async def _dispatch(self, action: str, params: dict, guild: discord.Guild) -> dict:
        handlers = {
            "move_user": self._move_user,
            "mute": self._mute,
            "unmute": self._unmute,
            "deafen": self._deafen,
            "undeafen": self._undeafen,
            "disconnect": self._disconnect,
            "edit_channel": self._edit_channel,
        }
        handler = handlers.get(action)
        if not handler:
            return {"success": False, "action": action, "details": t("err.unknown_action", locale=self._locale, action=action)}
        return await handler(params, guild)

    async def _move_user(self, params: dict, guild: discord.Guild) -> dict:
        """メンバーをボイスチャンネルに移動させる。"""
        user_id = params.get("user_id")
        channel_id = params.get("channel_id")
        if not user_id:
            return {"success": False, "action": "move_user", "details": t("exec.missing_param", locale=self._locale, param="user_id")}
        if not channel_id:
            return {"success": False, "action": "move_user", "details": t("exec.missing_param", locale=self._locale, param="channel_id")}

        member = guild.get_member(user_id)
        if not member:
            return {"success": False, "action": "move_user", "details": t("not_found.member", locale=self._locale, id=user_id)}

        channel = guild.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            return {"success": False, "action": "move_user", "details": t("not_found.voice_channel", locale=self._locale, id=channel_id)}

        try:
            await member.move_to(channel)
            return {"success": True, "action": "move_user", "details": t("exec.vc.moved", locale=self._locale, member=member.display_name, channel=channel.name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "move_user", "details": str(e)}

    async def _mute(self, params: dict, guild: discord.Guild) -> dict:
        """メンバーをサーバーミュートにする。"""
        user_id = params.get("user_id")
        if not user_id:
            return {"success": False, "action": "mute", "details": t("exec.missing_param", locale=self._locale, param="user_id")}

        member = guild.get_member(user_id)
        if not member:
            return {"success": False, "action": "mute", "details": t("not_found.member", locale=self._locale, id=user_id)}

        try:
            await member.edit(mute=True)
            return {"success": True, "action": "mute", "details": t("exec.vc.muted", locale=self._locale, member=member.display_name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "mute", "details": str(e)}

    async def _unmute(self, params: dict, guild: discord.Guild) -> dict:
        """メンバーのサーバーミュートを解除する。"""
        user_id = params.get("user_id")
        if not user_id:
            return {"success": False, "action": "unmute", "details": t("exec.missing_param", locale=self._locale, param="user_id")}

        member = guild.get_member(user_id)
        if not member:
            return {"success": False, "action": "unmute", "details": t("not_found.member", locale=self._locale, id=user_id)}

        try:
            await member.edit(mute=False)
            return {"success": True, "action": "unmute", "details": t("exec.vc.unmuted", locale=self._locale, member=member.display_name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "unmute", "details": str(e)}

    async def _deafen(self, params: dict, guild: discord.Guild) -> dict:
        """メンバーをサーバー聴覚禁止にする。"""
        user_id = params.get("user_id")
        if not user_id:
            return {"success": False, "action": "deafen", "details": t("exec.missing_param", locale=self._locale, param="user_id")}

        member = guild.get_member(user_id)
        if not member:
            return {"success": False, "action": "deafen", "details": t("not_found.member", locale=self._locale, id=user_id)}

        try:
            await member.edit(deafen=True)
            return {"success": True, "action": "deafen", "details": t("exec.vc.deafened", locale=self._locale, member=member.display_name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "deafen", "details": str(e)}

    async def _undeafen(self, params: dict, guild: discord.Guild) -> dict:
        """メンバーのサーバー聴覚禁止を解除する。"""
        user_id = params.get("user_id")
        if not user_id:
            return {"success": False, "action": "undeafen", "details": t("exec.missing_param", locale=self._locale, param="user_id")}

        member = guild.get_member(user_id)
        if not member:
            return {"success": False, "action": "undeafen", "details": t("not_found.member", locale=self._locale, id=user_id)}

        try:
            await member.edit(deafen=False)
            return {"success": True, "action": "undeafen", "details": t("exec.vc.undeafened", locale=self._locale, member=member.display_name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "undeafen", "details": str(e)}

    async def _disconnect(self, params: dict, guild: discord.Guild) -> dict:
        """メンバーをボイスチャンネルから切断する。"""
        user_id = params.get("user_id")
        if not user_id:
            return {"success": False, "action": "disconnect", "details": t("exec.missing_param", locale=self._locale, param="user_id")}

        member = guild.get_member(user_id)
        if not member:
            return {"success": False, "action": "disconnect", "details": t("not_found.member", locale=self._locale, id=user_id)}

        try:
            await member.move_to(None)
            return {"success": True, "action": "disconnect", "details": t("exec.vc.disconnected", locale=self._locale, member=member.display_name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "disconnect", "details": str(e)}

    async def _edit_channel(self, params: dict, guild: discord.Guild) -> dict:
        """ボイスチャンネルの設定を編集する。"""
        channel_id = params.get("channel_id")
        if not channel_id:
            return {"success": False, "action": "edit_channel", "details": t("exec.missing_param", locale=self._locale, param="channel_id")}

        channel = guild.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            return {"success": False, "action": "edit_channel", "details": t("not_found.voice_channel", locale=self._locale, id=channel_id)}

        kwargs: dict = {}
        if "name" in params:
            kwargs["name"] = params["name"]
        if "bitrate" in params:
            kwargs["bitrate"] = params["bitrate"]
        if "user_limit" in params:
            kwargs["user_limit"] = params["user_limit"]

        if not kwargs:
            return {"success": False, "action": "edit_channel", "details": t("exec.no_editable_params", locale=self._locale)}

        try:
            await channel.edit(**kwargs)
            return {"success": True, "action": "edit_channel", "details": t("exec.vc.edited", locale=self._locale, name=channel.name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit_channel", "details": str(e)}
