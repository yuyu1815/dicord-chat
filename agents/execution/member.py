import discord

from agents.base import MultiActionExecutionAgent
from graph.state import AgentState
from i18n import t


class MemberExecutionAgent(MultiActionExecutionAgent):
    """メンバー管理（ニックネーム・ロール・タイムアウト・キック・BAN）を行うエージェント。"""

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "edit_nickname": ["manage_nicknames"],
        "edit_roles": ["manage_roles"],
        "timeout": ["moderate_members"],
        "kick": ["kick_members"],
        "ban": ["ban_members"],
        "unban": ["ban_members"],
    }

    @property
    def name(self) -> str:
        return "member_execution"

    async def _dispatch(self, action: str, params: dict, guild: discord.Guild) -> dict:
        handlers = {
            "edit_nickname": self._edit_nickname,
            "edit_roles": self._edit_roles,
            "timeout": self._timeout,
            "kick": self._kick,
            "ban": self._ban,
            "unban": self._unban,
        }
        handler = handlers.get(action)
        if not handler:
            return {"success": False, "action": action, "details": t("err.unknown_action", locale=self._locale, action=action)}
        return await handler(params, guild)

    async def _edit_nickname(self, params: dict, guild: discord.Guild) -> dict:
        """メンバーのニックネームを変更する。"""
        member_id = params.get("member_id")
        nickname = params.get("nickname")
        if not member_id:
            return {"success": False, "action": "edit_nickname", "details": t("exec.missing_param", locale=self._locale, param="member_id")}

        member = guild.get_member(member_id)
        if not member:
            return {"success": False, "action": "edit_nickname", "details": t("not_found.member", locale=self._locale, id=member_id)}

        try:
            await member.edit(nick=nickname)
            if nickname:
                return {"success": True, "action": "edit_nickname", "details": t("exec.member.nickname_set", locale=self._locale, name=member.display_name, nickname=nickname)}
            return {"success": True, "action": "edit_nickname", "details": t("exec.member.nickname_reset", locale=self._locale, name=member.display_name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit_nickname", "details": str(e)}

    async def _edit_roles(self, params: dict, guild: discord.Guild) -> dict:
        """メンバーのロールを一括変更する。"""
        member_id = params.get("member_id")
        if not member_id:
            return {"success": False, "action": "edit_roles", "details": t("exec.missing_param", locale=self._locale, param="member_id")}

        member = guild.get_member(member_id)
        if not member:
            return {"success": False, "action": "edit_roles", "details": t("not_found.member", locale=self._locale, id=member_id)}

        add_role_ids = params.get("add_roles", [])
        remove_role_ids = params.get("remove_roles", [])

        add_roles = []
        for rid in add_role_ids:
            role = guild.get_role(rid)
            if role:
                add_roles.append(role)

        remove_roles = []
        for rid in remove_role_ids:
            role = guild.get_role(rid)
            if role:
                remove_roles.append(role)

        if not add_roles and not remove_roles:
            return {"success": False, "action": "edit_roles", "details": t("exec.member.no_roles", locale=self._locale)}

        try:
            await member.edit(roles=[r for r in member.roles if r not in remove_roles] + add_roles)
            parts = []
            if add_roles:
                parts.append(t("exec.member.roles_added", locale=self._locale, count=len(add_roles)))
            if remove_roles:
                parts.append(t("exec.member.roles_removed", locale=self._locale, count=len(remove_roles)))
            return {"success": True, "action": "edit_roles", "details": t("exec.member.roles_edited", locale=self._locale, name=member.display_name, details=", ".join(parts))}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit_roles", "details": str(e)}

    async def _timeout(self, params: dict, guild: discord.Guild) -> dict:
        """メンバーをタイムアウト（ミュート）する。"""
        member_id = params.get("member_id")
        duration_minutes = params.get("duration_minutes")
        reason = params.get("reason")
        if not member_id:
            return {"success": False, "action": "timeout", "details": t("exec.missing_param", locale=self._locale, param="member_id")}
        if duration_minutes is None:
            return {"success": False, "action": "timeout", "details": t("exec.missing_param", locale=self._locale, param="duration_minutes")}

        member = guild.get_member(member_id)
        if not member:
            return {"success": False, "action": "timeout", "details": t("not_found.member", locale=self._locale, id=member_id)}

        from datetime import datetime, timedelta, timezone
        until = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)

        try:
            await member.edit(timed_out_until=until, reason=reason)
            return {"success": True, "action": "timeout", "details": t("exec.member.timed_out", locale=self._locale, name=member.display_name, minutes=duration_minutes)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "timeout", "details": str(e)}

    async def _kick(self, params: dict, guild: discord.Guild) -> dict:
        """メンバーをキックする。"""
        member_id = params.get("member_id")
        reason = params.get("reason")
        if not member_id:
            return {"success": False, "action": "kick", "details": t("exec.missing_param", locale=self._locale, param="member_id")}

        member = guild.get_member(member_id)
        if not member:
            return {"success": False, "action": "kick", "details": t("not_found.member", locale=self._locale, id=member_id)}

        try:
            await member.kick(reason=reason)
            return {"success": True, "action": "kick", "details": t("exec.member.kicked", locale=self._locale, name=member.display_name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "kick", "details": str(e)}

    async def _ban(self, params: dict, guild: discord.Guild) -> dict:
        """メンバーをBANする。"""
        member_id = params.get("member_id")
        reason = params.get("reason")
        delete_message_days = params.get("delete_message_days", 0)
        if not member_id:
            return {"success": False, "action": "ban", "details": t("exec.missing_param", locale=self._locale, param="member_id")}

        member = guild.get_member(member_id)
        if not member:
            return {"success": False, "action": "ban", "details": t("not_found.member", locale=self._locale, id=member_id)}

        try:
            await member.ban(reason=reason, delete_message_days=delete_message_days)
            return {"success": True, "action": "ban", "details": t("exec.member.banned", locale=self._locale, name=member.display_name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "ban", "details": str(e)}

    async def _unban(self, params: dict, guild: discord.Guild) -> dict:
        """ユーザーのBANを解除する。"""
        user_id = params.get("user_id")
        reason = params.get("reason")
        if not user_id:
            return {"success": False, "action": "unban", "details": t("exec.missing_param", locale=self._locale, param="user_id")}

        user = discord.Object(id=user_id)
        try:
            await guild.unban(user, reason=reason)
            return {"success": True, "action": "unban", "details": t("exec.member.unbanned", locale=self._locale, user_id=user_id)}
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
            return {"success": False, "action": "unban", "details": str(e)}
