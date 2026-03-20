import discord

from agents.base import MultiActionExecutionAgent
from graph.state import AgentState


class ForumExecutionAgent(MultiActionExecutionAgent):
    """フォーラムチャンネルの操作（投稿・タグ管理）を行うエージェント。"""

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "create_post": ["send_messages"],
        "edit_post": ["manage_messages"],
        "delete_post": ["manage_threads"],
        "create_tag": ["manage_channels"],
        "edit_tag": ["manage_channels"],
        "delete_tag": ["manage_channels"],
    }

    @property
    def name(self) -> str:
        return "forum_execution"

    async def _dispatch(self, action: str, params: dict, guild: discord.Guild) -> dict:
        handlers = {
            "create_post": self._create_post,
            "edit_post": self._edit_post,
            "delete_post": self._delete_post,
            "create_tag": self._create_tag,
            "edit_tag": self._edit_tag,
            "delete_tag": self._delete_tag,
        }
        handler = handlers.get(action)
        if not handler:
            return {"success": False, "action": action, "details": f"Unknown action: {action}"}
        return await handler(params, guild)

    async def _get_forum_channel(self, guild: discord.Guild, channel_id: int) -> discord.ForumChannel | None:
        """チャンネルIDからフォーラムチャンネルを取得する。"""
        channel = guild.get_channel(channel_id)
        if isinstance(channel, discord.ForumChannel):
            return channel
        return None

    async def _create_post(self, params: dict, guild: discord.Guild) -> dict:
        """フォーラムに投稿を作成する。"""
        forum_id = params.get("forum_channel_id")
        title = params.get("title")
        content = params.get("content", "")
        if not forum_id:
            return {"success": False, "action": "create_post", "details": "Missing 'forum_channel_id' parameter"}
        if not title:
            return {"success": False, "action": "create_post", "details": "Missing 'title' parameter"}

        forum = await self._get_forum_channel(guild, forum_id)
        if not forum:
            return {"success": False, "action": "create_post", "details": f"Forum channel {forum_id} not found"}

        applied_tags = []
        tags_list = params.get("tags_list", [])
        available_tags = {t.id: t for t in forum.available_tags}
        for tag_id in tags_list:
            tag = available_tags.get(int(tag_id))
            if tag:
                applied_tags.append(tag)

        try:
            thread = await forum.create_thread(
                name=title,
                content=content,
                applied_tags=applied_tags,
            )
            return {"success": True, "action": "create_post", "details": f"Created forum post '{title}' ({thread.id})"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "create_post", "details": str(e)}

    async def _edit_post(self, params: dict, guild: discord.Guild) -> dict:
        """フォーラム投稿を編集する。"""
        message_id = params.get("message_id")
        if not message_id:
            return {"success": False, "action": "edit_post", "details": "Missing 'message_id' parameter"}

        content = params.get("content")
        if not content:
            return {"success": False, "action": "edit_post", "details": "Missing 'content' parameter"}

        try:
            for channel in guild.text_channels:
                if isinstance(channel, discord.ForumChannel):
                    for thread in channel.threads:
                        if thread.owner_id:
                            msg = thread.get_partial_message(message_id)
                            await msg.edit(content=content)
                            return {"success": True, "action": "edit_post", "details": f"Edited forum post message {message_id}"}

            return {"success": False, "action": "edit_post", "details": f"Could not find forum post with message {message_id}"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit_post", "details": str(e)}

    async def _delete_post(self, params: dict, guild: discord.Guild) -> dict:
        """フォーラム投稿を削除する。"""
        message_id = params.get("message_id")
        if not message_id:
            return {"success": False, "action": "delete_post", "details": "Missing 'message_id' parameter"}

        try:
            for channel in guild.text_channels:
                if isinstance(channel, discord.ForumChannel):
                    for thread in channel.threads:
                        if thread.id == message_id or thread.starter_message_id == message_id:
                            thread_name = thread.name
                            await thread.delete()
                            return {"success": True, "action": "delete_post", "details": f"Deleted forum post '{thread_name}'"}

            return {"success": False, "action": "delete_post", "details": f"Could not find forum post with message {message_id}"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "delete_post", "details": str(e)}

    async def _create_tag(self, params: dict, guild: discord.Guild) -> dict:
        """フォーラムにタグを作成する。"""
        forum_id = params.get("forum_channel_id")
        tag_name = params.get("name")
        if not forum_id:
            return {"success": False, "action": "create_tag", "details": "Missing 'forum_channel_id' parameter"}
        if not tag_name:
            return {"success": False, "action": "create_tag", "details": "Missing 'name' parameter"}

        forum = await self._get_forum_channel(guild, forum_id)
        if not forum:
            return {"success": False, "action": "create_tag", "details": f"Forum channel {forum_id} not found"}

        emoji = params.get("emoji")

        try:
            tag = await forum.create_tag(name=tag_name, emoji=emoji)
            return {"success": True, "action": "create_tag", "details": f"Created tag '{tag_name}' ({tag.id})"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "create_tag", "details": str(e)}

    async def _edit_tag(self, params: dict, guild: discord.Guild) -> dict:
        """フォーラムのタグを編集する。"""
        forum_id = params.get("forum_channel_id")
        tag_id = params.get("tag_id")
        if not forum_id:
            return {"success": False, "action": "edit_tag", "details": "Missing 'forum_channel_id' parameter"}
        if not tag_id:
            return {"success": False, "action": "edit_tag", "details": "Missing 'tag_id' parameter"}

        forum = await self._get_forum_channel(guild, forum_id)
        if not forum:
            return {"success": False, "action": "edit_tag", "details": f"Forum channel {forum_id} not found"}

        tag = next((t for t in forum.available_tags if t.id == int(tag_id)), None)
        if not tag:
            return {"success": False, "action": "edit_tag", "details": f"Tag {tag_id} not found in forum"}

        kwargs: dict = {}
        if "name" in params:
            kwargs["name"] = params["name"]
        if "emoji" in params:
            kwargs["emoji"] = params["emoji"]

        if not kwargs:
            return {"success": False, "action": "edit_tag", "details": "No editable parameters provided"}

        try:
            await tag.edit(**kwargs)
            return {"success": True, "action": "edit_tag", "details": f"Edited tag to '{kwargs.get('name', tag.name)}'"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "edit_tag", "details": str(e)}

    async def _delete_tag(self, params: dict, guild: discord.Guild) -> dict:
        """フォーラムのタグを削除する。"""
        forum_id = params.get("forum_channel_id")
        tag_id = params.get("tag_id")
        if not forum_id:
            return {"success": False, "action": "delete_tag", "details": "Missing 'forum_channel_id' parameter"}
        if not tag_id:
            return {"success": False, "action": "delete_tag", "details": "Missing 'tag_id' parameter"}

        forum = await self._get_forum_channel(guild, forum_id)
        if not forum:
            return {"success": False, "action": "delete_tag", "details": f"Forum channel {forum_id} not found"}

        tag = next((t for t in forum.available_tags if t.id == int(tag_id)), None)
        if not tag:
            return {"success": False, "action": "delete_tag", "details": f"Tag {tag_id} not found in forum"}

        tag_name = tag.name
        try:
            await tag.delete()
            return {"success": True, "action": "delete_tag", "details": f"Deleted tag '{tag_name}'"}
        except (discord.Forbidden, discord.HTTPException) as e:
            return {"success": False, "action": "delete_tag", "details": str(e)}
