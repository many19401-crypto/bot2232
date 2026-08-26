import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from config.settings import Settings
from music.player import LoopMode, MusicPlayer, PlayerState
from music.track import Track


class FakeVoice:
    def __init__(self):
        self.channel = Mock()
        self.source = None
        self.callback = None
        self.playing = True
        self.paused = False

    def is_connected(self):
        return True

    def is_playing(self):
        return self.playing

    def is_paused(self):
        return self.paused

    def stop(self):
        self.playing = False
        if self.callback:
            self.callback(None)

    def play(self, source, after):
        self.source = source
        self.callback = after
        self.playing = True


@pytest.mark.asyncio
async def test_concurrent_skip_does_not_start_two_callbacks(monkeypatch):
    settings = Settings(discord_token="test", database_url="sqlite+aiosqlite://")
    guild = Mock(id=1)
    extractor = Mock()
    voice = Mock()
    ffmpeg = Mock()
    player = MusicPlayer(guild, settings, extractor, voice, ffmpeg)
    player.voice_client = FakeVoice()
    player.current = Track(1, "https://example/1", "one")
    player.voice_client.callback = player._audio_finished
    player.state = PlayerState.PLAYING
    advance = AsyncMock()
    monkeypatch.setattr(player, "_advance_locked", advance)

    results = await asyncio.gather(player.skip(), player.skip())
    await asyncio.sleep(0)
    assert results == [True, False]
    assert advance.await_count == 1
    player._watchdog.cancel()


@pytest.mark.asyncio
async def test_loop_modes_are_cycled():
    settings = Settings(discord_token="test")
    player = MusicPlayer(Mock(id=1), settings, Mock(), Mock(), Mock())
    assert await player.toggle_loop() == LoopMode.TRACK
    assert await player.toggle_loop() == LoopMode.QUEUE
    assert await player.toggle_loop() == LoopMode.OFF
    player._watchdog.cancel()
