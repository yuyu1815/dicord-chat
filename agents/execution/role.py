import discord

from i18n import t

from agents.base import MultiActionExecutionAgent
from graph.state import AgentState


class RoleExecutionAgent(MultiActionExecutionAgent):
    """ロールの作成・編集・削除・並び替え・付与・剥奪を行うエージェント。"""

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "create": ["manage_roles"],
        "edit": ["manage_roles"],
        "delete": ["manage_roles"],
        "reorder": ["manage_roles"],
        "assign": ["manage_roles"],
        "revoke": ["manage_roles"],
    }

    @property
    def name(self) -> str:
        return "role_execution"

    async def _dispatch(self, action: str, params: dict, guild: discord.Guild) -> dict:
        handlers = {
            "create": self._create,
            "edit": self._edit,
            "delete": self._delete,
            "reorder": self._reorder,
            "assign": self._assign,
            "revoke": self._revoke,
        }
        handler = handlers.get(action)
        if not handler:
            return {"success": False, "action": action, "details": t("err.unknown_action", locale=self._locale, action=action)}
        return await handler(params, guild)

    async def _create(self, params: dict, guild: discord.Guild) -> dict:
        """ロールを作成する。"""
        name = params.get("name")
        if not name:
            return {"success": False, "action": "create", "details": t("exec.missing_param", locale=self._locale, param="name")}

        kwargs: dict = {"name": name}

        if "color" in params:
            kwargs["colour"] = params["color"]
        if "permissions" in params:
            kwargs["permissions"] = discord.Permissions(params["permissions"])
        if "hoist" in params:
            kwargs["hoist"] = params["hoist"]
        if "mentionable" in params:
            kwargs["mentionable"] = params["mentionable"]

        try:
            role = await guild.create_role(**kwargs)
            return {"success": True, "action": "create", "details": t("exec.role.created", locale=self._locale, name=role.name, id=role.id)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "create", "details": str(e)}

    async def _edit(self, params: dict, guild: discord.Guild) -> dict:
        """ロールを編集する。"""
        role_id = params.get("role_id")
        if not role_id:
            return {"success": False, "action": "edit", "details": t("exec.missing_param", locale=self._locale, param="role_id")}

        role = guild.get_role(role_id)
        if not role:
            return {"success": False, "action": "edit", "details": t("not_found.role", locale=self._locale, id=role_id)}

        kwargs: dict = {}
        if "name" in params:
            kwargs["name"] = params["name"]
        if "color" in params:
            kwargs["colour"] = params["color"]
        if "permissions" in params:
            kwargs["permissions"] = discord.Permissions(params["permissions"])
        if "hoist" in params:
            kwargs["hoist"] = params["hoist"]
        if "mentionable" in params:
            kwargs["mentionable"] = params["mentionable"]

        if not kwargs:
            return {"success": False, "action": "edit", "details": t("exec.no_editable_params", locale=self._locale)}

        try:
            await role.edit(**kwargs)
            return {"success": True, "action": "edit", "details": t("exec.role.edited", locale=self._locale, name=role.name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit", "details": str(e)}

    async def _delete(self, params: dict, guild: discord.Guild) -> dict:
        """ロールを削除する。"""
        role_id = params.get("role_id")
        if not role_id:
            return {"success": False, "action": "delete", "details": t("exec.missing_param", locale=self._locale, param="role_id")}

        role = guild.get_role(role_id)
        if not role:
            return {"success": False, "action": "delete", "details": t("not_found.role", locale=self._locale, id=role_id)}

        role_name = role.name
        try:
            await role.delete()
            return {"success": True, "action": "delete", "details": t("exec.role.deleted", locale=self._locale, name=role_name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "delete", "details": str(e)}

    async def _reorder(self, params: dict, guild: discord.Guild) -> dict:
        """ロールの並び順を変更する。"""
        roles = params.get("roles", [])
        if not roles:
            return {"success": False, "action": "reorder", "details": t("exec.missing_param", locale=self._locale, param="roles")}

        try:
            await guild.edit_role_positions(roles)
            return {"success": True, "action": "reorder", "details": t("exec.role.reordered", locale=self._locale, count=len(roles))}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "reorder", "details": str(e)}

    async def _assign(self, params: dict, guild: discord.Guild) -> dict:
        """メンバーにロールを付与する。"""
        member_id = params.get("member_id")
        role_id = params.get("role_id")
        if not member_id:
            return {"success": False, "action": "assign", "details": t("exec.missing_param", locale=self._locale, param="member_id")}
        if not role_id:
            return {"success": False, "action": "assign", "details": t("exec.missing_param", locale=self._locale, param="role_id")}

        member = guild.get_member(member_id)
        if not member:
            return {"success": False, "action": "assign", "details": t("not_found.member", locale=self._locale, id=member_id)}

        role = guild.get_role(role_id)
        if not role:
            return {"success": False, "action": "assign", "details": t("not_found.role", locale=self._locale, id=role_id)}

        try:
            await member.add_roles(role)
            return {"success": True, "action": "assign", "details": t("exec.role.assigned", locale=self._locale, role=role.name, member=member.display_name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "assign", "details": str(e)}

    async def _revoke(self, params: dict, guild: discord.Guild) -> dict:
        """メンバーからロールを剥奪する。"""
        member_id = params.get("member_id")
        role_id = params.get("role_id")
        if not member_id:
            return {"success": False, "action": "revoke", "details": t("exec.missing_param", locale=self._locale, param="member_id")}
        if not role_id:
            return {"success": False, "action": "revoke", "details": t("exec.missing_param", locale=self._locale, param="role_id")}

        member = guild.get_member(member_id)
        if not member:
            return {"success": False, "action": "revoke", "details": t("not_found.member", locale=self._locale, id=member_id)}

        role = guild.get_role(role_id)
        if not role:
            return {"success": False, "action": "revoke", "details": t("not_found.role", locale=self._locale, id=role_id)}

        try:
            await member.remove_roles(role)
            return {"success": True, "action": "revoke", "details": t("exec.role.revoked", locale=self._locale, role=role.name, member=member.display_name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "revoke", "details": str(e)}
