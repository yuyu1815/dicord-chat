import discord

from i18n import t

from agents.base import MultiActionExecutionAgent
from graph.state import AgentState


class PermissionExecutionAgent(MultiActionExecutionAgent):
    """チャンネル権限オーバーライドの設定・削除・同期を行うエージェント。"""

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "set_channel_permission": ["manage_roles"],
        "delete_channel_permission": ["manage_roles"],
        "sync_permissions": ["manage_roles"],
    }

    @property
    def name(self) -> str:
        return "permission_execution"

    async def _dispatch(self, action: str, params: dict, guild: discord.Guild) -> dict:
        handlers = {
            "set_channel_permission": self._set_channel_permission,
            "delete_channel_permission": self._delete_channel_permission,
            "sync_permissions": self._sync_permissions,
        }
        handler = handlers.get(action)
        if not handler:
            return {"success": False, "action": action, "details": t("err.unknown_action", locale=self._locale, action=action)}
        return await handler(params, guild)

    def _resolve_target(self, guild: discord.Guild, target_type: str, target_id: int) -> discord.Role | discord.Member | None:
        """target_type に応じてロールまたはメンバーを取得する。"""
        if target_type == "member":
            return guild.get_member(target_id)
        return guild.get_role(target_id)

    async def _set_channel_permission(self, params: dict, guild: discord.Guild) -> dict:
        """チャンネルの権限オーバーライドを設定する。"""
        channel_id = params.get("channel_id")
        target_type = params.get("target_type", "role")
        target_id = params.get("target_id")
        if not channel_id:
            return {"success": False, "action": "set_channel_permission", "details": t("exec.missing_param", locale=self._locale, param="channel_id")}
        if not target_id:
            return {"success": False, "action": "set_channel_permission", "details": t("exec.missing_param", locale=self._locale, param="target_id")}

        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "set_channel_permission", "details": t("not_found.channel", locale=self._locale, id=channel_id)}

        target = self._resolve_target(guild, target_type, target_id)
        if not target:
            label = "Member" if target_type == "member" else "Role"
            return {"success": False, "action": "set_channel_permission", "details": t("exec.permission.label_not_found", locale=self._locale, label=label, id=target_id)}

        allow_perms = params.get("allow_perms", 0)
        deny_perms = params.get("deny_perms", 0)

        overwrite = discord.PermissionOverwrite(
            allow=discord.Permissions(allow_perms),
            deny=discord.Permissions(deny_perms),
        )

        try:
            await channel.set_permissions(target, overwrite=overwrite)
            target_name = target.display_name if hasattr(target, "display_name") else target.name
            return {"success": True, "action": "set_channel_permission", "details": t("exec.permission.set", locale=self._locale, target=target_name, channel=channel.name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "set_channel_permission", "details": str(e)}

    async def _delete_channel_permission(self, params: dict, guild: discord.Guild) -> dict:
        """チャンネルの権限オーバーライドを削除する。"""
        channel_id = params.get("channel_id")
        overwrite_id = params.get("overwrite_id")
        if not channel_id:
            return {"success": False, "action": "delete_channel_permission", "details": t("exec.missing_param", locale=self._locale, param="channel_id")}
        if not overwrite_id:
            return {"success": False, "action": "delete_channel_permission", "details": t("exec.missing_param", locale=self._locale, param="overwrite_id")}

        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "delete_channel_permission", "details": t("not_found.channel", locale=self._locale, id=channel_id)}

        target = guild.get_role(overwrite_id) or guild.get_member(overwrite_id)
        if not target:
            return {"success": False, "action": "delete_channel_permission", "details": t("exec.permission.target_not_found", locale=self._locale, id=overwrite_id)}

        try:
            await channel.set_permissions(target, overwrite=None)
            target_name = target.display_name if hasattr(target, "display_name") else target.name
            return {"success": True, "action": "delete_channel_permission", "details": t("exec.permission.cleared", locale=self._locale, target=target_name, channel=channel.name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "delete_channel_permission", "details": str(e)}

    async def _sync_permissions(self, params: dict, guild: discord.Guild) -> dict:
        """チャンネルの権限をカテゴリと同期する。"""
        channel_id = params.get("channel_id")
        category_id = params.get("category_id")
        if not channel_id:
            return {"success": False, "action": "sync_permissions", "details": t("exec.missing_param", locale=self._locale, param="channel_id")}

        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "sync_permissions", "details": t("not_found.channel", locale=self._locale, id=channel_id)}

        if category_id:
            category = guild.get_channel(category_id)
            if category and isinstance(category, discord.CategoryChannel):
                try:
                    await channel.edit(category=category)
                except (discord.Forbidden, discord.HTTPException):
                    return {"success": False, "action": "sync_permissions", "details": t("exec.permission.move_failed", locale=self._locale, id=category_id)}

        try:
            await channel.edit(sync_permissions=True)
            return {"success": True, "action": "sync_permissions", "details": t("exec.permission.synced", locale=self._locale, channel=channel.name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "sync_permissions", "details": str(e)}
