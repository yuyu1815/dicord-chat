import discord

from agents.base import InvestigationAgent
from graph.state import AgentState
from i18n import t

KEY_PERMISSIONS = [
    "administrator",
    "manage_guild",
    "manage_channels",
    "manage_messages",
    "manage_roles",
    "kick_members",
    "ban_members",
    "send_messages",
    "read_messages",
    "connect",
    "speak",
]


class PermissionInvestigationAgent(InvestigationAgent):
    """権限設定を調査するエージェント。"""

    @property
    def name(self) -> str:
        return "permission_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        """サーバー全体またはチャンネル別の権限設定を収集する。

        Args:
            state: ワークフロー状態（``channel_id`` がある場合はチャンネル権限を調査）。
            guild: 対象サーバー。

        Returns:
            権限スコープと権限一覧を含む辞書。
        """
        channel_id = state.get("channel_id")

        if channel_id is None:
            return self._guild_level_permissions(guild)

        channel = guild.get_channel(channel_id)
        if channel is None:
            return {"error": t("inv.channel_not_found", locale=state.get("locale", "en"), id=channel_id)}

        return await self._channel_overwrites(channel, guild)

    def _guild_level_permissions(self, guild: discord.Guild) -> dict:
        """サーバー全体のロール権限一覧を取得する。"""
        role_perms = []
        for role in guild.roles:
            perms = role.permissions
            summary = {perm: getattr(perms, perm, False) for perm in KEY_PERMISSIONS}
            role_perms.append({
                "role_id": role.id,
                "role_name": role.name,
                "permissions": summary,
            })
        return {"scope": "guild", "roles": role_perms}

    async def _channel_overwrites(
        self, channel: discord.abc.GuildChannel, guild: discord.Guild
    ) -> dict:
        """チャンネルの権限オーバーライド一覧を取得する。"""
        overwrites = []
        for target, overwrite in channel.overwrites.items():
            is_role = isinstance(target, discord.Role)
            perms = overwrite.pair()

            allowed = [p for p, v in perms[0] if v]
            denied = [p for p, v in perms[1] if v]

            overwrites.append({
                "target_id": target.id,
                "target_name": target.name if is_role else str(target),
                "target_type": "role" if is_role else "member",
                "allowed": allowed,
                "denied": denied,
            })

        return {
            "scope": "channel",
            "channel_id": channel.id,
            "channel_name": channel.name,
            "overwrites": overwrites,
        }
