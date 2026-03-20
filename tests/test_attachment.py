"""Tests for services/attachment.py"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.attachment import (
    AttachmentError,
    fetch_attachment_bytes,
    fetch_image_bytes,
    fetch_audio_bytes,
    fetch_url_bytes,
    _is_private_ip,
)


def _make_attachment(filename="test.png", content_type="image/png", size=1024):
    att = MagicMock()
    att.filename = filename
    att.content_type = content_type
    att.size = size
    att.read = AsyncMock(return_value=b"fake-data")
    return att


def _make_message(*attachments):
    msg = MagicMock()
    msg.attachments = list(attachments)
    return msg


@pytest.mark.asyncio
async def test_fetch_by_filename():
    channel = MagicMock()
    att = _make_attachment("photo.png")
    channel.fetch_message = AsyncMock(return_value=_make_message(att))

    filename, data = await fetch_attachment_bytes(channel, 123, filename="photo.png")
    assert filename == "photo.png"
    assert data == b"fake-data"


@pytest.mark.asyncio
async def test_fetch_by_index():
    channel = MagicMock()
    att = _make_attachment("photo.png")
    channel.fetch_message = AsyncMock(return_value=_make_message(att))

    filename, data = await fetch_attachment_bytes(channel, 123, index=0)
    assert filename == "photo.png"


@pytest.mark.asyncio
async def test_filename_not_found():
    channel = MagicMock()
    att = _make_attachment("photo.png")
    channel.fetch_message = AsyncMock(return_value=_make_message(att))

    with pytest.raises(AttachmentError, match="not found"):
        await fetch_attachment_bytes(channel, 123, filename="wrong.png")


@pytest.mark.asyncio
async def test_index_out_of_range():
    channel = MagicMock()
    att = _make_attachment("photo.png")
    channel.fetch_message = AsyncMock(return_value=_make_message(att))

    with pytest.raises(AttachmentError, match="out of range"):
        await fetch_attachment_bytes(channel, 123, index=5)


@pytest.mark.asyncio
async def test_message_not_found():
    import discord
    channel = MagicMock()
    channel.fetch_message = AsyncMock(side_effect=discord.NotFound(MagicMock(), "not found"))

    with pytest.raises(AttachmentError, match="not found"):
        await fetch_attachment_bytes(channel, 123)


@pytest.mark.asyncio
async def test_no_attachments():
    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=_make_message())

    with pytest.raises(AttachmentError, match="no attachments"):
        await fetch_attachment_bytes(channel, 123, filename="x.png")


@pytest.mark.asyncio
async def test_disallowed_content_type():
    channel = MagicMock()
    att = _make_attachment("script.js", content_type="application/javascript")
    channel.fetch_message = AsyncMock(return_value=_make_message(att))

    with pytest.raises(AttachmentError, match="Disallowed type"):
        await fetch_image_bytes(channel, 123, filename="script.js")


@pytest.mark.asyncio
async def test_size_limit():
    channel = MagicMock()
    att = _make_attachment("big.png", size=100 * 1024 * 1024)
    channel.fetch_message = AsyncMock(return_value=_make_message(att))

    with pytest.raises(AttachmentError, match="exceeds limit"):
        await fetch_image_bytes(channel, 123, filename="big.png")


@pytest.mark.asyncio
async def test_image_only_allows_image():
    channel = MagicMock()
    att = _make_attachment("audio.mp3", content_type="audio/mpeg")
    channel.fetch_message = AsyncMock(return_value=_make_message(att))

    with pytest.raises(AttachmentError, match="Disallowed type"):
        await fetch_image_bytes(channel, 123, filename="audio.mp3")


@pytest.mark.asyncio
async def test_audio_only_allows_audio():
    channel = MagicMock()
    att = _make_attachment("photo.png", content_type="image/png")
    channel.fetch_message = AsyncMock(return_value=_make_message(att))

    with pytest.raises(AttachmentError, match="Disallowed type"):
        await fetch_audio_bytes(channel, 123, filename="photo.png")


# --- fetch_url_bytes tests ---

def test_is_private_ip_localhost():
    assert _is_private_ip("localhost") is True
    assert _is_private_ip("127.0.0.1") is True


def test_is_private_ip_public():
    assert _is_private_ip("example.com") is False


def test_is_private_ip_invalid():
    assert _is_private_ip("nonexistent.invalid") is False


@pytest.mark.asyncio
async def test_url_disallowed_scheme():
    with pytest.raises(AttachmentError, match="Disallowed scheme"):
        await fetch_url_bytes("http://example.com/img.png")


@pytest.mark.asyncio
async def test_url_private_ip_blocked():
    with patch("services.attachment._is_private_ip", return_value=True):
        with pytest.raises(AttachmentError, match="private IP"):
            await fetch_url_bytes("https://example.com/img.png")


@pytest.mark.asyncio
async def test_url_invalid_no_hostname():
    with pytest.raises(AttachmentError, match="no hostname"):
        await fetch_url_bytes("https:///img.png")


def _make_fake_session(resp_status=200, resp_type="image/png", chunks=None):
    """aiohttp.ClientSession のモック。"""

    class FakeReader:
        async def iter_chunked(self, size):
            for chunk in (chunks if chunks is not None else [b"img-data"]):
                yield chunk

    class FakeResponse:
        status = resp_status
        headers = {"Content-Type": resp_type, "Content-Length": str(sum(len(c) for c in chunks) if chunks else 7)}

        @property
        def content(self):
            return FakeReader()

    class FakeGetCM:
        async def __aenter__(self):
            return FakeResponse()
        async def __aexit__(self, *args):
            pass

    class FakeSession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        def get(self, url):
            return FakeGetCM()

    return FakeSession()


@pytest.mark.asyncio
async def test_url_successful_download():
    import services.attachment as att_mod
    original = att_mod.aiohttp.ClientSession
    att_mod.aiohttp.ClientSession = lambda **kwargs: _make_fake_session()
    try:
        data = await fetch_url_bytes("https://example.com/img.png")
    finally:
        att_mod.aiohttp.ClientSession = original
    assert data == b"img-data"


@pytest.mark.asyncio
async def test_url_size_limit():
    import services.attachment as att_mod
    original = att_mod.aiohttp.ClientSession
    big_chunk = b"x" * (26 * 1024 * 1024)
    att_mod.aiohttp.ClientSession = lambda **kwargs: _make_fake_session(chunks=[big_chunk])
    try:
        with pytest.raises(AttachmentError, match="exceeds"):
            await fetch_url_bytes("https://example.com/img.png")
    finally:
        att_mod.aiohttp.ClientSession = original
