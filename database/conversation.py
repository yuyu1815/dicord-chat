"""会話履歴の永続化と取得。ユーザー×サーバー単位で直近Nターンを保持する。"""

import json
from pathlib import Path
from typing import Any

import aiosqlite

_LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"

MAX_HISTORY_TURNS = 5


async def save_conversation_turn(
    db_path: str,
    *,
    user_id: int,
    guild_id: int,
    session_id: str,
    request: str,
    response: str,
) -> None:
    """1ターンの会話（リクエスト+レスポンス）を保存する。

    Args:
        db_path: SQLite DB パス。
        user_id: ユーザーID。
        guild_id: サーバーID。
        session_id: approval_id（JSONLレコードとの紐付け用）。
        request: ユーザーの入力テキスト。
        response: ボットの返却テキスト。
    """
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO conversation_history "
            "(user_id, guild_id, session_id, request, response, created_at) "
            "VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (user_id, guild_id, session_id, request, response),
        )
        await db.commit()


async def load_conversation_history(
    db_path: str,
    *,
    user_id: int,
    guild_id: int,
    limit: int = MAX_HISTORY_TURNS,
) -> list[dict[str, Any]]:
    """直近の会話履歴を取得する（古い順）。

    Args:
        db_path: SQLite DB パス。
        user_id: ユーザーID。
        guild_id: サーバーID。
        limit: 取得件数。

    Returns:
        履歴エントリのリスト。
    """
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT session_id, request, response "
            "FROM conversation_history "
            "WHERE user_id = ? AND guild_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (user_id, guild_id, limit),
        )
        rows = await cursor.fetchall()
    return [
        {
            "session_id": row[0],
            "request": row[1],
            "response": row[2],
        }
        for row in reversed(rows)
    ]


def load_session_detail(guild_id: int, user_id: int, session_id: str) -> str:
    """指定セッションのJSONL詳細ログを読み込む。

    Args:
        guild_id: サーバーID。
        user_id: ユーザーID。
        session_id: 取得対象のapproval_id。

    Returns:
        フォーマットされたログテキスト。
    """
    log_path = _LOGS_DIR / str(guild_id) / str(user_id) / f"{session_id}_ai_io.jsonl"
    if not log_path.exists():
        return f"Log file not found for session {session_id}."

    records: list[dict[str, Any]] = []
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                records.append(record)
            except json.JSONDecodeError:
                continue

    if not records:
        return f"No records found in session {session_id}."

    parts: list[str] = []
    for record in records:
        kind = record.get("kind", "unknown")
        parts.append(f"[{kind}]")
        for msg in record.get("messages", []):
            content = msg.get("content", "")
            if len(content) > 1500:
                content = content[:1500] + "..."
            parts.append(f"  {msg.get('type', '?')}: {content}")
        resp = record.get("response", "")
        if resp:
            if len(resp) > 1500:
                resp = resp[:1500] + "..."
            parts.append(f"  Response: {resp}")
        parsed = record.get("parsed")
        if parsed:
            parsed_str = json.dumps(parsed, ensure_ascii=False)
            if len(parsed_str) > 1500:
                parsed_str = parsed_str[:1500] + "..."
            parts.append(f"  Parsed: {parsed_str}")

    return "\n".join(parts)
