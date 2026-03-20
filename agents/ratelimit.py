"""チャンネル名・トピック変更のレート制限トラッカー。

Discord APIはチャンネル名/トピック変更に 2回/10分 のサブレート制限を持つ。
この制限は PATCH /channels/{channel_id} エンドポイントの name/topic パラメータに
適用され、**チャンネルごと**に独立。nsfw/slowmode 等の変更とは別バケット。

複数のエージェント（Channel, Category, VoiceChannel）で共有して使用する。
"""

import time

# 2回/10分のサブレート制限（チャンネルごと）
_EDIT_LIMIT = 2
_WINDOW = 600  # seconds (10 minutes)

# channel_id -> list[timestamp]
_history: dict[int, list[float]] = {}


def check_rate_limit(channel_id: int, locale: str = "en") -> dict | None:
    """名前/トピック変更のレート制限をチェックする。

    Args:
        channel_id: 対象チャンネルのID。
        locale: ロケールコード。

    Returns:
        制限に達している場合はエラー結果辞書、それ以外は ``None``。
    """
    now = time.monotonic()
    timestamps = _history.get(channel_id, [])
    timestamps[:] = [ts for ts in timestamps if now - ts < _WINDOW]
    if len(timestamps) >= _EDIT_LIMIT:
        from i18n import t
        return {
            "success": False,
            "action": "edit",
            "details": t("ratelimit.channel_edit_name_topic", locale=locale),
        }
    return None


def record_edit(channel_id: int) -> None:
    """名前/トピック変更を実行したことを記録する。

    Args:
        channel_id: 対象チャンネルのID。
    """
    _history.setdefault(channel_id, []).append(time.monotonic())
