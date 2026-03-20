import discord

from agents.base import MultiActionExecutionAgent
from i18n import t


class CategoryExecutionAgent(MultiActionExecutionAgent):
    """カテゴリ（チャンネルグループ）の操作を行うエージェント。"""

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "create": ["manage_channels"],
        "edit": ["manage_channels"],
        "delete": ["manage_channels"],
    }

    @property
    def name(self) -> str:
        return "category_execution"

    async def _dispatch(self, action: str, params: dict, guild: discord.Guild) -> dict:
        handlers = {
            "create": self._create,
            "edit": self._edit,
            "delete": self._delete,
        }
        handler = handlers.get(action)
        if not handler:
            return {"success": False, "action": action, "details": t("err.unknown_action", locale=self._locale, action=action)}
        return await handler(params, guild)

    async def _create(self, params: dict, guild: discord.Guild) -> dict:
        """カテゴリを作成する。"""
        name = params.get("name")
        if not name:
            return {"success": False, "action": "create", "details": t("exec.missing_param", locale=self._locale, param="name")}

        overwrites = []
        raw_overwrites = params.get("overwrites", [])
        for ow in raw_overwrites:
            target_id = ow.get("target_id")
            target_type = ow.get("target_type", "role")
            allow = ow.get("allow", 0)
            deny = ow.get("deny", 0)
            if target_type == "member":
                target = guild.get_member(target_id)
            else:
                target = guild.get_role(target_id)
            if not target:
                continue
            overwrites.append(
                discord.PermissionOverwrite(
                    target=target,
                    allow=discord.Permissions(allow),
                    deny=discord.Permissions(deny),
                )
            )

        kwargs = {"name": name}
        if params.get("position") is not None:
            kwargs["position"] = params["position"]
        if overwrites:
            kwargs["overwrites"] = overwrites

        try:
            category = await guild.create_category_channel(**kwargs)
            return {"success": True, "action": "create", "details": t("exec.category.created", locale=self._locale, name=category.name, id=category.id)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "create", "details": str(e)}

    async def _edit(self, params: dict, guild: discord.Guild) -> dict:
        """カテゴリを編集する。"""
        category_id = params.get("category_id")
        if not category_id:
            return {"success": False, "action": "edit", "details": t("exec.missing_param", locale=self._locale, param="category_id")}
        category = guild.get_channel(category_id)
        if not category or not isinstance(category, discord.CategoryChannel):
            return {"success": False, "action": "edit", "details": t("not_found.category", locale=self._locale, id=category_id)}

        kwargs = {}
        if "name" in params:
            kwargs["name"] = params["name"]
        if "position" in params:
            kwargs["position"] = params["position"]

        if not kwargs:
            return {"success": False, "action": "edit", "details": t("exec.no_editable_params", locale=self._locale)}

        try:
            await category.edit(**kwargs)
            return {"success": True, "action": "edit", "details": t("exec.category.edited", locale=self._locale, name=category.name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit", "details": str(e)}

    async def _delete(self, params: dict, guild: discord.Guild) -> dict:
        """カテゴリを削除する。"""
        category_id = params.get("category_id")
        if not category_id:
            return {"success": False, "action": "delete", "details": t("exec.missing_param", locale=self._locale, param="category_id")}
        category = guild.get_channel(category_id)
        if not category or not isinstance(category, discord.CategoryChannel):
            return {"success": False, "action": "delete", "details": t("not_found.category", locale=self._locale, id=category_id)}
        category_name = category.name
        try:
            await category.delete()
            return {"success": True, "action": "delete", "details": t("exec.category.deleted", locale=self._locale, name=category_name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "delete", "details": str(e)}
