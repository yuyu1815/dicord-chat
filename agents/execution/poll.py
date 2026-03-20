import datetime

import discord

from agents.base import MultiActionExecutionAgent
from i18n import t


class PollExecutionAgent(MultiActionExecutionAgent):
    """投票の作成・終了を行うエージェント。"""

    ACTION_PERMISSIONS: dict[str, list[str]] = {
        "create": ["send_messages"],
        "end": ["manage_messages"],
    }

    @property
    def name(self) -> str:
        return "poll_execution"

    async def _dispatch(self, action: str, params: dict, guild: discord.Guild) -> dict:
        handlers = {
            "create": self._create,
            "end": self._end,
        }
        handler = handlers.get(action)
        if not handler:
            return {"success": False, "action": action, "details": t("err.unknown_action", locale=self._locale, action=action)}
        return await handler(params, guild)

    async def _create(self, params: dict, guild: discord.Guild) -> dict:
        """投票を作成して送信する。"""
        channel_id = params.get("channel_id")
        question = params.get("question")
        answers = params.get("answers")

        if not channel_id:
            return {"success": False, "action": "create", "details": t("exec.missing_param", locale=self._locale, param="channel_id")}
        if not question:
            return {"success": False, "action": "create", "details": t("exec.poll.missing_question", locale=self._locale)}
        if not answers:
            return {"success": False, "action": "create", "details": t("exec.poll.missing_answers", locale=self._locale)}

        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "create", "details": t("not_found.channel", locale=self._locale, id=channel_id)}

        duration_hours = params.get("duration", 24)
        poll = discord.Poll(
            question=discord.PollMedia(text=question),
            duration=datetime.timedelta(hours=duration_hours),
            multiple=params.get("multiple", False),
        )
        for answer in answers:
            poll.add_answer(text=answer["text"], emoji=answer.get("emoji"))

        kwargs = {"poll": poll}
        if "content" in params:
            kwargs["content"] = params["content"]

        message = await channel.send(**kwargs)
        return {"success": True, "action": "create", "details": t("exec.poll.created", locale=self._locale, channel=channel.name, id=message.id)}

    async def _end(self, params: dict, guild: discord.Guild) -> dict:
        """投票を終了する。"""
        channel_id = params.get("channel_id")
        message_id = params.get("message_id")

        if not channel_id or not message_id:
            return {"success": False, "action": "end", "details": t("exec.missing_param", locale=self._locale, param="channel_id or message_id")}

        channel = guild.get_channel(channel_id)
        if not channel:
            return {"success": False, "action": "end", "details": t("not_found.channel", locale=self._locale, id=channel_id)}

        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            return {"success": False, "action": "end", "details": t("not_found.message", locale=self._locale, id=message_id)}

        if not message.poll:
            return {"success": False, "action": "end", "details": t("exec.poll.not_a_poll", locale=self._locale)}

        await message.poll.end()
        return {"success": True, "action": "end", "details": t("exec.poll.ended", locale=self._locale, channel=channel.name, id=message.id)}
