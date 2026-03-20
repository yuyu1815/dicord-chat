"""チャンネル名・トピック変更のレート制限トラッカー。

Discord APIはチャンネル名/トピック変更に 2回/10分 のサブレート制限を持つ。
この制限は PATCH /channels/{channel_id} エンドポイントの name/topic パラメータに
適用され、nsfw/slowmode 等の変更とは別バケット。

複数のエージェント（Channel, Category, VoiceChannel）で共有して使用する。
"""

import time

# 2回/10分のサブレート制限
_EDIT_LIMIT = 2
_WINDOW = 600  # seconds (10 minutes)

_history: list[float] = []


def check_rate_limit(locale: str = "en") -> dict | None:
    """名前/トピック変更のレート制限をチェックする。

    Returns:
        制限に達している場合はエラー結果辞書、それ以外は ``None``。
    """
    now = time.monotonic()
    _history[:] = [ts for ts in _history if now - ts < _WINDOW]
    if len(_history) >= _EDIT_LIMIT:
        from i18n import t
        return {
            "success": False,
            "action": "edit",
            "details": t("ratelimit.channel_edit_name_topic", locale=locale),
        }
    return None


def record_edit() -> None:
    """名前/トピック変更を実行したことを記録する。"""
    _history.append(time.monotonic())
