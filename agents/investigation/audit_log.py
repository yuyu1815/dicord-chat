import discord

from agents.base import InvestigationAgent
from graph.state import AgentState

MAX_DEFAULT_ENTRIES = 20


class AuditLogInvestigationAgent(InvestigationAgent):
    """監査ログを調査するエージェント。"""

    @property
    def name(self) -> str:
        return "audit_log_investigation"

    async def investigate(self, state: AgentState, guild: discord.Guild) -> dict:
        """サーバーの監査ログを取得する。

        Args:
            state: ワークフロー状態。
            guild: 対象サーバー。

        Returns:
            監査ログエントリのリスト。
        """
        limit = MAX_DEFAULT_ENTRIES
        if "request" in state and state["request"]:
            try:
                limit = int(state["request"])
            except (ValueError, TypeError):
                limit = MAX_DEFAULT_ENTRIES

        entries = []
        async for entry in guild.audit_logs(limit=limit):
            target_name = None
            if entry.target:
                target_name = getattr(entry.target, "display_name", None) or getattr(entry.target, "name", str(entry.target))

            user_name = entry.user.display_name if entry.user else None

            changes = []
            if entry.before or entry.after:
                if entry.before:
                    changes.append({"type": "before", "data": str(entry.before)[:200]})
                if entry.after:
                    changes.append({"type": "after", "data": str(entry.after)[:200]})

            entries.append({
                "action_type": str(entry.action),
                "user": user_name,
                "target": target_name,
                "reason": entry.reason,
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
                "changes": changes if changes else None,
            })

        return {"audit_log_entries": entries}
