import discord

from agents.base import InvestigationAgent
from graph.state import AgentState


class PollInvestigationAgent(InvestigationAgent):
    """アクティブな投票を調査するエージェント。"""

    @property
    def name(self) -> str:
        return "poll_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        """テキストチャンネルの最近のメッセージからアクティブな投票を収集する。"""
        polls = []
        for channel in guild.text_channels:
            try:
                async for message in channel.history(limit=100):
                    if message.poll and not message.poll.has_ended:
                        answers = []
                        for answer in message.poll.answers:
                            answers.append({
                                "text": answer.text,
                                "votes": answer.vote_count,
                            })
                        polls.append({
                            "id": message.id,
                            "channel": channel.name,
                            "channel_id": channel.id,
                            "question": message.poll.question.text if message.poll.question else None,
                            "answers": answers,
                            "total_votes": message.poll.total_votes,
                            "expires_at": str(message.poll.expires_at) if message.poll.expires_at else None,
                        })
            except discord.Forbidden:
                continue

        return {"polls": polls, "total_count": len(polls)}
