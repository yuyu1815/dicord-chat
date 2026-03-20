"""ファイルダウンロードユーティリティ。

メッセージ添付ファイル（message_id + channel_id）と外部URLの両方に対応。
外部URLからのダウンロードは aiohttp で行い、プライベートIPへのSSRF対策を含む。

全APIがbytesを直接受け付けるため、ディスクへの保存は行わない。
"""

import asyncio
import io
import ipaddress
import logging
import socket
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
import av
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
    max_duration: float | None = None,
) -> tuple[str, bytes]:
    """メッセージから音声をダウンロードする。

    Args:
        channel: テキストチャンネル。
        message_id: メッセージID。
        filename: 指定ファイル名（省略時はindex）。
        index: 添付ファイルのインデックス。
        max_duration: 最大秒数。超過時はPyAVで切り捨てる（例: 5.0）。
            指定時はDiscord CDN URLからストリーミングダウンロードし、
            ファイルサイズ制限を無視して切り捨てを行う。
    """
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
    if not any(content_type.startswith(p) for p in _ALLOWED_AUDIO_PREFIXES):
        raise AttachmentError(f"Disallowed type '{content_type}' for '{attachment.filename}'")

    # max_duration指定時はURL経由でストリーミング+切り捨て（サイズ制限を回避）
    if max_duration is not None:
        data = await _stream_and_truncate(attachment.url, attachment.filename, max_duration)
        return attachment.filename, data

    if attachment.size > MAX_DOWNLOAD_SIZE:
        raise AttachmentError(f"'{attachment.filename}' ({attachment.size}B) exceeds limit ({MAX_DOWNLOAD_SIZE}B)")

    try:
        data = await attachment.read()
    except HTTPException as e:
        raise AttachmentError(f"Failed to download '{attachment.filename}': {e.text}")

    return attachment.filename, data


async def _stream_and_truncate(url: str, source_name: str, max_duration: float) -> bytes:
    """Discord CDN URLからストリーミングダウンロードしつつPyAVでmax_duration秒に切り捨てる。

    出力は常にMP3（discord.pyの制限によりOGGは弾かれるため）。
    """
    try:
        return await asyncio.to_thread(_stream_and_truncate_sync, url, source_name, max_duration)
    except Exception as e:
        raise AttachmentError(f"Audio download/truncation failed: {e}")


def _stream_and_truncate_sync(url: str, source_name: str, max_duration: float) -> bytes:
    """同期的にHTTPストリーミングで読み込み、MP3に切り捨てる。"""
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "DiscordBot/1.0"})
    resp = urllib.request.urlopen(req, timeout=30)

    container = av.open(resp)

    input_stream = None
    for s in container.streams:
        if s.type == "audio":
            input_stream = s
            break
    if input_stream is None:
        raise ValueError("No audio stream found")

    in_fmt = container.format.name if container.format and container.format.name else _get_output_format(source_name)

    # MP3入力はストリームコピー（再エンコードなし）、それ以外はlibmp3lameで再エンコード
    if in_fmt == "mp3":
        return _truncate_mp3_mux(container, input_stream, max_duration)
    else:
        return _truncate_to_mp3(container, input_stream, max_duration)


def _truncate_mp3_mux(container, input_stream, max_duration: float) -> bytes:
    """MP3ストリームコピー（再エンコードなし）でmax_duration秒に切り捨てる。

    PyAV 17.0+ の add_mux_stream() を使用。
    """
    output_buf = io.BytesIO()
    output_container = av.open(output_buf, mode="w", format="mp3")
    out_stream = output_container.add_mux_stream(
        codec_name="mp3",
        time_base=input_stream.time_base,
        rate=input_stream.sample_rate,
    )

    max_pts = int(max_duration / input_stream.time_base)

    for packet in container.demux(input_stream):
        if packet.dts is None:
            continue
        if (packet.pts is not None and packet.pts >= max_pts) or \
           (packet.dts is not None and packet.dts >= max_pts):
            break
        packet.stream = out_stream
        output_container.mux(packet)

    output_container.close()
    return output_buf.getvalue()


def _truncate_to_mp3(container, input_stream, max_duration: float) -> bytes:
    """libmp3lameでMP3に再エンコードしつつmax_duration秒に切り捨てる。

    非MP3フォーマット（OGG, WAV, M4A等）の入力に使用。
    """
    output_buf = io.BytesIO()
    output_container = av.open(output_buf, mode="w", format="mp3")
    output_stream = output_container.add_stream(codec_name="libmp3lame", rate=input_stream.sample_rate)

    max_ts = int(max_duration / input_stream.time_base)
    truncated = False

    for packet in container.demux(input_stream):
        if truncated:
            break
        for frame in packet.decode():
            if frame.pts >= max_ts:
                truncated = True
                break
            frame.pts = None
            for opacket in output_stream.encode(frame):
                output_container.mux(opacket)

    for opacket in output_stream.encode():
        output_container.mux(opacket)

    output_container.close()
    return output_buf.getvalue()


async def fetch_url_audio_bytes(
    url: str,
    max_duration: float | None = None,
    max_size: int = MAX_DOWNLOAD_SIZE,
) -> bytes:
    """外部URLから音声をダウンロードする。max_duration指定時は切り捨てる。"""
    data = await fetch_url_bytes(url, allowed_types=_ALLOWED_AUDIO_PREFIXES, max_size=max_size)
    if max_duration is not None:
        data = await truncate_audio(data, url.split("/")[-1], max_duration)
    return data


def _get_output_format(filename: str) -> str:
    """ファイル名から拡張子を取得してフォーマット名に変換する。"""
    ext = Path(filename).suffix.lower().lstrip(".")
    return ext if ext else "mp3"


async def truncate_audio(data: bytes, source_name: str, max_duration: float) -> bytes:
    """PyAVで音声をmax_duration秒に切り捨てる。出力はMP3。"""
    try:
        return await asyncio.to_thread(_truncate_audio_sync, data, source_name, max_duration)
    except Exception as e:
        logger.warning("Audio truncation failed, using original: %s", e)
        return data


def _truncate_audio_sync(data: bytes, source_name: str, max_duration: float) -> bytes:
    """同期的にPyAVで音声を切り捨てる。出力は常にMP3。"""
    input_buf = io.BytesIO(data)
    container = av.open(input_buf)

    input_stream = None
    for s in container.streams:
        if s.type == "audio":
            input_stream = s
            break
    if input_stream is None:
        raise ValueError("No audio stream found")

    in_fmt = container.format.name if container.format and container.format.name else _get_output_format(source_name)

    if in_fmt == "mp3":
        return _truncate_mp3_mux(container, input_stream, max_duration)
    else:
        return _truncate_to_mp3(container, input_stream, max_duration)
