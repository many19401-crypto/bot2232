import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from config.settings import Settings
from music.extractor import ExtractorError
from music.player import LoopMode, MusicPlayer, PlayerState
from music.track import Track


class VoiceStub:
    def __init__(self):
        self.channel = Mock(members=[])
        self.source = None
        self._playing = False
        self.after = None

    def is_connected(self):
        return True

    def is_playing(self):
        return self._playing

    def is_paused(self):
        return False

    def play(self, source, after):
        self.source = source
        self.after = after
        self._playing = True

    def stop(self):
        self._playing = False
        if self.after:
            self.after(None)


def make_player(settings=None):
    settings = settings or Settings(discord_token="test")
    extractor = Mock()
    extractor.resolve_stream = AsyncMock(return_value="https://stream.example/live")
    ffmpeg = Mock()
    ffmpeg.create.return_value = Mock()
    player = MusicPlayer(Mock(id=1), settings, extractor, Mock(), ffmpeg)
    player.voice_client = VoiceStub()
    return player, extractor


@pytest.mark.asyncio
async def test_concurrent_add_is_serialized_by_player_lock():
    player, _ = make_player(Settings(discord_token="test", default_max_queue_size=25))
    tracks = [Track(1, f"https://example/{i}", str(i)) for i in range(20)]
    await asyncio.gather(*(player.add_track(item) for item in tracks))
    assert len(player.queue) + (1 if player.current else 0) == 20
    player._watchdog.cancel()


@pytest.mark.asyncio
async def test_ffmpeg_or_extractor_failure_skips_only_bad_track():
    player, extractor = make_player()
    first = Track(1, "https://example/bad", "bad")
    second = Track(1, "https://example/good", "good")
    extractor.resolve_stream = AsyncMock(
        side_effect=[ExtractorError("unavailable"), "https://stream.example/good"]
    )
    await player.enqueue([first, second])
    await player.start(Mock())
    assert player.current is second
    assert player.state == PlayerState.PLAYING
    player._watchdog.cancel()


@pytest.mark.asyncio
async def test_queue_loop_requeues_the_previous_track():
    player, extractor = make_player()
    track = Track(1, "https://example/loop", "loop")
    await player.enqueue([track])
    await player.start(Mock())
    player.loop_mode = LoopMode.QUEUE
    player.voice_client._playing = False
    await player.on_audio_finished(None)
    assert player.current is track
    assert extractor.resolve_stream.await_count == 2
    player._watchdog.cancel()
