import discord

from agents.base import InvestigationAgent
from graph.state import AgentState
from i18n import t

DEFAULT_MEMBER_LIMIT = 50


class MemberInvestigationAgent(InvestigationAgent):
    """メンバー情報を調査するエージェント。"""

    @property
    def name(self) -> str:
        return "member_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        """メンバー情報を収集する。``user_id`` がある場合は個別、なければ一覧を取得する。

        Args:
            state: ワークフロー状態。
            guild: 対象サーバー。

        Returns:
            メンバー情報の辞書。
        """
        target_user_id = state.get("user_id")

        if target_user_id is not None:
            return await self._single_member(guild, target_user_id, state)

        return await self._member_list(guild)

    async def _single_member(self, guild: discord.Guild, user_id: int, state: AgentState) -> dict:
        """指定メンバーの詳細情報を取得する。"""
        member = guild.get_member(user_id)

        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except discord.NotFound:
                return {"error": t("inv.member_not_found", locale=state.get("locale", "en"), id=user_id)}
            except discord.Forbidden:
                return {"error": t("inv.member_no_permission", locale=state.get("locale", "en"), id=user_id)}

        activities = member.activities or []
        activity_info = None
        for activity in activities:
            if isinstance(activity, discord.BaseActivity):
                activity_info = {"name": activity.name, "type": str(activity.type)}
                break

        return {
            "id": member.id,
            "name": member.name,
            "display_name": member.display_name,
            "nick": member.nick,
            "avatar_url": member.display_avatar.url if member.display_avatar else None,
            "joined_at": member.joined_at.isoformat() if member.joined_at else None,
            "created_at": member.created_at.isoformat(),
            "top_role": member.top_role.name,
            "roles": [role.name for role in member.roles if not role.is_default()],
            "status": str(member.status) if member.status else None,
            "activity": activity_info,
            "bot": member.bot,
        }

    async def _member_list(self, guild: discord.Guild) -> dict:
        """メンバー一覧を取得する（上限 ``DEFAULT_MEMBER_LIMIT`` 件）。"""
        members = []
        async for member in guild.fetch_members(limit=DEFAULT_MEMBER_LIMIT):
            members.append({
                "id": member.id,
                "name": member.name,
                "display_name": member.display_name,
                "nick": member.nick,
                "top_role": member.top_role.name,
                "joined_at": member.joined_at.isoformat() if member.joined_at else None,
                "bot": member.bot,
            })

        return {
            "members": members,
            "fetched_count": len(members),
            "total_members": guild.member_count,
        }
