import discord

from agents.base import SingleActionExecutionAgent
from graph.state import AgentState
from i18n import t
from services.attachment import AttachmentError, fetch_image_bytes, fetch_url_bytes

NAME = "emoji_execution"


class EmojiExecutionAgent(SingleActionExecutionAgent):
    # Emoji操作は通常と異なるギルド単位の厳しいレート制限がある
    ACTION_COOLDOWN: float = 15.0

    ACTION_HANDLERS: dict[str, str] = {
        "create": "Create emoji",
        "edit": "Edit emoji",
        "delete": "Delete emoji",
    }

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "create": ["manage_emojis_and_stickers"],
        "edit": ["manage_emojis_and_stickers"],
        "delete": ["manage_emojis_and_stickers"],
    }

    not_found_message: str = "Emoji not found."

    @property
    def name(self) -> str:
        return NAME

    def _resolve_image(self, params: dict) -> bytes:
        image = params.get("image")
        if not image:
            raise ValueError(t("exec.emoji.data_required", locale=self._locale))
        if isinstance(image, bytes):
            return image
        raise ValueError(t("exec.emoji.data_required", locale=self._locale))

    async def _do_create(self, guild: discord.Guild, params: dict) -> dict:
        image = params.get("image")
        url = params.get("url")
        message_id = params.get("message_id")

        # 優先度: bytes > message_id > url
        if image is None and message_id:
            channel_id = params.get("channel_id")
            if not channel_id:
                return {"success": False, "action": "create", "details": t("exec.missing_param", locale=self._locale, param="channel_id")}
            channel = guild.get_channel(channel_id)
            if not channel or not isinstance(channel, (discord.TextChannel, discord.Thread)):
                return {"success": False, "action": "create", "details": t("not_found.channel", locale=self._locale, id=channel_id)}
            try:
                _, image = await fetch_image_bytes(channel, message_id, filename=params.get("filename"))
            except AttachmentError as e:
                return {"success": False, "action": "create", "details": str(e.reason)}

        if image is None and url:
            try:
                image = await fetch_url_bytes(url, allowed_types=("image/",))
            except AttachmentError as e:
                return {"success": False, "action": "create", "details": str(e.reason)}

        try:
            image = self._resolve_image({"image": image})
        except ValueError as e:
            return {"success": False, "action": "create", "details": str(e)}

        kwargs: dict = {"name": params["name"], "image": image}
        if "roles" in params:
            roles = [guild.get_role(r) for r in params["roles"]]
            kwargs["roles"] = [r for r in roles if r is not None]

        try:
            emoji = await guild.create_custom_emoji(**kwargs)
            return {"success": True, "action": "create", "details": t("exec.emoji.created", locale=self._locale, name=emoji.name)}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "create", "details": str(e)}

    async def _do_edit(self, guild: discord.Guild, params: dict) -> dict:
        emoji = guild.get_emoji(params["emoji_id"])
        if not emoji:
            return {"success": False, "action": "edit", "details": t("exec.emoji.not_found", locale=self._locale)}

        kwargs: dict = {}
        if "name" in params:
            kwargs["name"] = params["name"]
        if "roles" in params:
            roles = [guild.get_role(r) for r in params["roles"]]
            kwargs["roles"] = [r for r in roles if r is not None]

        await emoji.edit(**kwargs)
        return {"success": True, "action": "edit", "details": t("exec.emoji.edited", locale=self._locale, name=emoji.name)}

    async def _do_delete(self, guild: discord.Guild, params: dict) -> dict:
        emoji = guild.get_emoji(params["emoji_id"])
        if not emoji:
            return {"success": False, "action": "delete", "details": t("exec.emoji.not_found", locale=self._locale)}
        await emoji.delete()
        return {"success": True, "action": "delete", "details": t("exec.emoji.deleted", locale=self._locale, name=emoji.name)}
