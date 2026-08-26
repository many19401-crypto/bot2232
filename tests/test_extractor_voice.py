from unittest.mock import AsyncMock, Mock

import pytest

from config.settings import Settings
from music.extractor import ExtractorError, MediaExtractor
from music.voice import VoiceConnector


@pytest.mark.asyncio
async def test_extractor_converts_provider_failures_to_domain_error(monkeypatch):
    extractor = MediaExtractor(Settings(discord_token="test"))
    monkeypatch.setattr(extractor, "_extract", Mock(side_effect=RuntimeError("provider down")))
    with pytest.raises(ExtractorError, match="could not be reached"):
        await extractor.search("test", 1, 2, "user")


@pytest.mark.asyncio
async def test_voice_connector_uses_bounded_retries():
    settings = Settings(discord_token="test", voice_reconnect_attempts=2)
    connector = VoiceConnector(settings)
    channel = Mock()
    channel.guild.voice_client = None
    channel.connect = AsyncMock(side_effect=asyncio_timeout())
    with pytest.raises(ConnectionError):
        await connector.connect(channel)
    assert channel.connect.await_count == 2


def asyncio_timeout():
    return TimeoutError("timeout")
