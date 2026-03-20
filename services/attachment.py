"""ファイルダウンロードユーティリティ。

メッセージ添付ファイル（message_id + channel_id）と外部URLの両方に対応。
外部URLからのダウンロードは aiohttp で行い、プライベートIPへのSSRF対策を含む。

全APIがbytesを直接受け付けるため、ディスクへの保存は行わない。
"""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

import aiohttp
import discord
from discord import HTTPException, NotFound, Forbidden

logger = logging.getLogger("discord_bot")

MAX_DOWNLOAD_SIZE = 25 * 1024 * 1024  # 25MB
DOWNLOAD_TIMEOUT = aiohttp.ClientTimeout(total=30)

_ALLOWED_IMAGE_PREFIXES = ("image/",)
_ALLOWED_AUDIO_PREFIXES = ("audio/",)
_ALLOWED_FILE_PREFIXES = _ALLOWED_IMAGE_PREFIXES + _ALLOWED_AUDIO_PREFIXES

# 外部URLダウンロード時に許可するscheme
_ALLOWED_SCHEMES = {"https"}


def _is_private_ip(hostname: str) -> bool:
    """ホスト名がプライベートIPに解決されるかチェックする（SSRF対策）。"""
    try:
        results = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    for family, _, _, _, sockaddr in results:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    return False


async def fetch_url_bytes(
    url: str,
    allowed_types: tuple[str, ...] = _ALLOWED_FILE_PREFIXES,
    max_size: int = MAX_DOWNLOAD_SIZE,
) -> bytes:
    """外部URLからダウンロードしてbytesを返す。

    Args:
        url: ダウンロード先URL。
        allowed_types: 許可するcontent_typeプレフィックス。
        max_size: ダウンロードサイズ上限。

    Returns:
        ファイルのbytes。

    Raises:
        AttachmentError: URLが無効・禁止・ダウンロード失敗の場合。
    """
    parsed = urlparse(url)
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise AttachmentError(f"Disallowed scheme '{parsed.scheme}'. Only HTTPS is allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise AttachmentError("Invalid URL: no hostname")

    if _is_private_ip(hostname):
        raise AttachmentError(f"URL resolves to private IP, blocked for security")

    headers = {"User-Agent": "DiscordBot/1.0 (image download)"}

    try:
        async with aiohttp.ClientSession(timeout=DOWNLOAD_TIMEOUT, headers=headers) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise AttachmentError(f"HTTP {resp.status} when downloading from '{hostname}'")

                content_type = resp.headers.get("Content-Type", "")
                if allowed_types and not any(content_type.startswith(p) for p in allowed_types):
                    raise AttachmentError(f"Disallowed type '{content_type}' from '{hostname}'")

                content_length = resp.headers.get("Content-Length")
                if content_length and int(content_length) > max_size:
                    raise AttachmentError(f"Content-Length {content_length} exceeds limit {max_size}")

                # ストリーミングで読み取り、サイズ上限を適用
                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.content.iter_chunked(1024 * 64):
                    total += len(chunk)
                    if total > max_size:
                        raise AttachmentError(f"Download exceeded {max_size}B limit")
                    chunks.append(chunk)

                return b"".join(chunks)
    except aiohttp.ClientError as e:
        raise AttachmentError(f"Download failed: {e}")


class AttachmentError(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


async def fetch_attachment_bytes(
    channel: discord.TextChannel | discord.Thread | discord.VoiceChannel,
    message_id: int,
    filename: str | None = None,
    index: int = 0,
    allowed_types: tuple[str, ...] | None = None,
    max_size: int = MAX_DOWNLOAD_SIZE,
) -> tuple[str, bytes]:
    """メッセージの添付ファイルをダウンロードしてbytesで返す。"""
    try:
        message = await channel.fetch_message(message_id)
    except NotFound:
        raise AttachmentError(f"Message {message_id} not found")
    except Forbidden:
        raise AttachmentError(f"No permission to read message {message_id}")
    except HTTPException as e:
        raise AttachmentError(f"Failed to fetch message {message_id}: {e.text}")

    if not message.attachments:
        raise AttachmentError(f"Message {message_id} has no attachments")

    attachment: discord.Attachment | None = None
    if filename is not None:
        for att in message.attachments:
            if att.filename == filename:
                attachment = att
                break
        if attachment is None:
            available = ", ".join(a.filename for a in message.attachments)
            raise AttachmentError(f"'{filename}' not found. Available: {available}")
    else:
        if index >= len(message.attachments):
            raise AttachmentError(f"Index {index} out of range ({len(message.attachments)} attachments)")
        attachment = message.attachments[index]

    content_type = attachment.content_type or ""
    if allowed_types and not any(content_type.startswith(p) for p in allowed_types):
        raise AttachmentError(f"Disallowed type '{content_type}' for '{attachment.filename}'")

    if attachment.size > max_size:
        raise AttachmentError(f"'{attachment.filename}' ({attachment.size}B) exceeds limit ({max_size}B)")

    try:
        data = await attachment.read()
    except HTTPException as e:
        raise AttachmentError(f"Failed to download '{attachment.filename}': {e.text}")

    return attachment.filename, data


async def fetch_image_bytes(
    channel: discord.TextChannel | discord.Thread,
    message_id: int,
    filename: str | None = None,
    index: int = 0,
) -> tuple[str, bytes]:
    """メッセージから画像をダウンロードする。"""
    return await fetch_attachment_bytes(channel, message_id, filename=filename, index=index, allowed_types=_ALLOWED_IMAGE_PREFIXES)


async def fetch_audio_bytes(
    channel: discord.TextChannel | discord.Thread,
    message_id: int,
    filename: str | None = None,
    index: int = 0,
) -> tuple[str, bytes]:
    """メッセージから音声をダウンロードする。"""
    return await fetch_attachment_bytes(channel, message_id, filename=filename, index=index, allowed_types=_ALLOWED_AUDIO_PREFIXES)
