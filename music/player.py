from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import discord

from config.settings import Settings
from database.repositories.library import HistoryRepository
from utils.compat import StrEnum

from .extractor import ExtractorError, MediaExtractor
from .ffmpeg import FFmpegFactory
from .queue import QueueError, TrackQueue
from .track import Track
from .voice import VoiceConnector

if TYPE_CHECKING:
    from services.cache import Cache

logger = logging.getLogger(__name__)


class PlayerState(StrEnum):
    IDLE = "idle"
    CONNECTING = "connecting"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPING = "stopping"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class LoopMode(StrEnum):
    OFF = "off"
    TRACK = "track"
    QUEUE = "queue"


PanelUpdater = Callable[["MusicPlayer", bool], Awaitable[None]]


class MusicPlayer:
    """One completely isolated playback session per guild."""

    def __init__(
        self,
        guild: discord.Guild,
        settings: Settings,
        extractor: MediaExtractor,
        voice: VoiceConnector,
        ffmpeg: FFmpegFactory,
        history: HistoryRepository | None = None,
        panel_updater: PanelUpdater | None = None,
        cache: Cache | None = None,
    ):
        self.guild = guild
        self.settings = settings
        self.extractor = extractor
        self.voice = voice
        self.ffmpeg = ffmpeg
        self.history = history
        self.panel_updater = panel_updater
        self.cache = cache
        self.queue = TrackQueue(settings.default_max_queue_size)
        self.current: Track | None = None
        self.voice_client: discord.VoiceClient | None = None
        self.state = PlayerState.IDLE
        self.volume = settings.default_volume / 100
        self.loop_mode = LoopMode.OFF
        self.autoplay = settings.default_autoplay
        self.auto_disconnect_timeout = settings.default_auto_disconnect_timeout
        self.text_channel: discord.abc.Messageable | None = None
        self.panel_message: discord.Message | None = None
        self.started_at: float | None = None
        self.paused_at: float | None = None
        self._paused_position = 0.0
        self._lock = asyncio.Lock()
        self._ignore_end_callbacks = 0
        self._skip_in_progress = False
        self._stopping = False
        self._autoplay_history: set[str] = set()
        self._played_history: deque[Track] = deque(maxlen=50)
        self._loop = asyncio.get_running_loop()
        self._last_error: str | None = None
        self._watchdog = asyncio.create_task(self._idle_watchdog())

    @property
    def queue_size(self) -> int:
        return len(self.queue)

    @property
    def position(self) -> float:
        if self.current is None:
            return 0.0
        if self.state == PlayerState.PAUSED:
            return self._paused_position
        if self.started_at is None:
            return self._paused_position
        return max(0.0, self._paused_position + time.monotonic() - self.started_at)

    async def connect(
        self, channel: discord.VoiceChannel | discord.StageChannel
    ) -> discord.VoiceClient:
        async with self._lock:
            self.state = PlayerState.CONNECTING
            try:
                self.voice_client = await self.voice.connect(channel)
                self._stopping = False
                self.state = PlayerState.IDLE if self.current is None else PlayerState.PLAYING
                return self.voice_client
            except Exception:
                self.state = PlayerState.ERROR
                raise

    async def add_track(self, track: Track, priority: bool = False) -> int:
        async with self._lock:
            position = self.queue.add(track, priority=priority)
            if self.state == PlayerState.IDLE and self.voice_client and self.current is None:
                await self._advance_locked()
            return position

    async def enqueue(self, tracks: list[Track], priority: bool = False) -> int:
        async with self._lock:
            total = self.queue.extend(tracks, priority=priority)
            if self.state == PlayerState.IDLE and self.voice_client and self.current is None:
                await self._advance_locked()
            return total

    async def start(self, text_channel: discord.abc.Messageable) -> None:
        async with self._lock:
            self.text_channel = text_channel
            if self.current is None and self.queue:
                await self._advance_locked()

    async def _advance_locked(self) -> None:
        if self._stopping:
            return
        if self.voice_client is None or not self.voice_client.is_connected():
            self.state = PlayerState.ERROR
            return
        if self.current is not None and (
            self.voice_client.is_playing() or self.voice_client.is_paused()
        ):
            return

        previous = self.current
        if previous is not None:
            await self._record_history(previous)
            self._played_history.append(previous)
            if self.loop_mode == LoopMode.TRACK:
                try:
                    self.queue.add(previous, priority=True)
                except QueueError:
                    logger.warning("Could not requeue looped track in guild=%s", self.guild.id)
            elif self.loop_mode == LoopMode.QUEUE:
                try:
                    self.queue.add(previous)
                except QueueError:
                    logger.warning("Could not requeue queue-loop track in guild=%s", self.guild.id)
            self.current = None

        if not self.queue:
            if self.autoplay and previous is not None:
                await self._append_autoplay_locked(previous)
            if not self.queue:
                self.state = PlayerState.IDLE
                self.started_at = None
                await self._update_panel(stopped=True)
                return

        attempts = min(len(self.queue), 5)
        for _ in range(attempts):
            track = self.queue.popleft()
            try:
                stream_url = await self.extractor.resolve_stream(track)
                source = self.ffmpeg.create(track, stream_url, self.volume)
                self.voice_client.play(source, after=self._audio_finished)
            except (ExtractorError, discord.ClientException, OSError) as exc:
                self._last_error = str(exc)
                logger.warning(
                    "Skipping track guild=%s title=%r: %s", self.guild.id, track.title, exc
                )
                continue
            except Exception as exc:
                self._last_error = str(exc)
                logger.exception(
                    "Unexpected playback error guild=%s title=%r", self.guild.id, track.title
                )
                continue
            self.current = track
            self.started_at = time.monotonic()
            self._paused_position = 0.0
            self.paused_at = None
            self.state = PlayerState.PLAYING
            await self._update_panel()
            return

        self.current = None
        self.state = PlayerState.ERROR
        await self._update_panel(stopped=True)
        if self.text_channel is not None:
            await self._safe_send("❌ Не удалось воспроизвести доступные треки. Очередь сохранена.")

    def _audio_finished(self, error: Exception | None) -> None:
        if error:
            logger.error("FFmpeg/audio error guild=%s: %s", self.guild.id, error)
        if self._loop.is_closed():
            return
        try:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.on_audio_finished(error))
            )
        except RuntimeError:
            logger.debug("Event loop closed before audio callback guild=%s", self.guild.id)

    async def on_audio_finished(self, error: Exception | None) -> None:
        async with self._lock:
            if self._ignore_end_callbacks:
                self._ignore_end_callbacks -= 1
                return
            if self._stopping:
                return
            self._skip_in_progress = False
            await self._advance_locked()

    async def pause(self) -> bool:
        async with self._lock:
            if not self.voice_client or not self.voice_client.is_playing() or self.current is None:
                return False
            self._paused_position = self.position
            self.paused_at = time.monotonic()
            self.voice_client.pause()
            self.state = PlayerState.PAUSED
            await self._update_panel()
            return True

    async def resume(self) -> bool:
        async with self._lock:
            if not self.voice_client or not self.voice_client.is_paused():
                return False
            self.voice_client.resume()
            self.started_at = time.monotonic()
            self.state = PlayerState.PLAYING
            await self._update_panel()
            return True

    async def skip(self) -> bool:
        async with self._lock:
            if self.current is None or self.voice_client is None or self._skip_in_progress:
                return False
            if self.voice_client.is_playing() or self.voice_client.is_paused():
                self._skip_in_progress = True
                self.voice_client.stop()
                return True
            await self._advance_locked()
            return True

    async def stop(self, disconnect: bool = False) -> None:
        async with self._lock:
            self._stopping = True
            self._skip_in_progress = False
            self.state = PlayerState.STOPPING
            self.queue.clear()
            if self.voice_client and (
                self.voice_client.is_playing() or self.voice_client.is_paused()
            ):
                self._ignore_end_callbacks += 1
                self.voice_client.stop()
            self.current = None
            self.started_at = None
            self._paused_position = 0
            if disconnect:
                await self.voice.disconnect(self.guild)
                self.voice_client = None
            self._stopping = False
            self.state = PlayerState.IDLE
            await self._update_panel(stopped=True)

    async def leave(self) -> None:
        await self.stop(disconnect=True)

    async def set_volume(self, percent: int) -> None:
        if not 0 <= percent <= 100:
            raise ValueError("Volume must be between 0 and 100")
        async with self._lock:
            self.volume = percent / 100
            if (
                self.voice_client
                and self.voice_client.source
                and isinstance(self.voice_client.source, discord.PCMVolumeTransformer)
            ):
                self.voice_client.source.volume = self.volume
            await self._update_panel()

    async def previous(self) -> bool:
        async with self._lock:
            if not self._played_history:
                return False
            previous = self._played_history.pop()
            if self.current is not None:
                self.queue.add(previous, priority=True)
            else:
                self.queue.add(previous, priority=True)
            if self.voice_client and (
                self.voice_client.is_playing() or self.voice_client.is_paused()
            ):
                self._ignore_end_callbacks += 1
                self.voice_client.stop()
            await self._advance_locked()
            return True

    async def seek(self, seconds: float) -> bool:
        async with self._lock:
            if (
                self.current is None
                or self.voice_client is None
                or not self.voice_client.is_connected()
            ):
                return False
            if self.current.duration is not None and not 0 <= seconds < self.current.duration:
                raise ValueError("Seek position is outside track duration")
            stream_url = await self.extractor.resolve_stream(self.current)
            was_active = self.voice_client.is_playing() or self.voice_client.is_paused()
            if was_active:
                self._ignore_end_callbacks += 1
                self.voice_client.stop()
            source = self.ffmpeg.create(self.current, stream_url, self.volume, seconds)
            self.voice_client.play(source, after=self._audio_finished)
            self._paused_position = seconds
            self.started_at = time.monotonic()
            self.state = PlayerState.PLAYING
            await self._update_panel()
            return True

    async def toggle_loop(self) -> LoopMode:
        async with self._lock:
            self.loop_mode = {
                LoopMode.OFF: LoopMode.TRACK,
                LoopMode.TRACK: LoopMode.QUEUE,
                LoopMode.QUEUE: LoopMode.OFF,
            }[self.loop_mode]
            await self._update_panel()
            return self.loop_mode

    async def shuffle(self) -> None:
        async with self._lock:
            self.queue.shuffle()
            await self._update_panel()

    async def remove(self, position: int) -> Track:
        async with self._lock:
            track = self.queue.remove(position)
            await self._update_panel()
            return track

    async def clear_queue(self) -> int:
        async with self._lock:
            count = len(self.queue)
            self.queue.clear()
            await self._update_panel()
            return count

    async def reconnect(self, channel: discord.VoiceChannel | discord.StageChannel) -> bool:
        async with self._lock:
            self.state = PlayerState.RECONNECTING
            try:
                self.voice_client = await self.voice.connect(channel)
                if self.current is not None:
                    stream_url = await self.extractor.resolve_stream(self.current)
                    source = self.ffmpeg.create(
                        self.current, stream_url, self.volume, self.position
                    )
                    self.voice_client.play(source, after=self._audio_finished)
                    self.started_at = time.monotonic()
                    self.state = PlayerState.PLAYING
                else:
                    self.state = PlayerState.IDLE
                await self._update_panel()
                return True
            except Exception as exc:
                self._last_error = str(exc)
                self.state = PlayerState.ERROR
                logger.exception("Voice reconnect failed guild=%s", self.guild.id)
                return False

    async def handle_voice_state(
        self, before: discord.VoiceChannel | None, after: discord.VoiceChannel | None
    ) -> None:
        if after is not None or before is None or self._stopping:
            return
        if self.current is not None or self.queue:
            await asyncio.sleep(1)
            await self.reconnect(before)

    async def _append_autoplay_locked(self, previous: Track) -> None:
        try:
            candidates = await self.extractor.related(
                previous, self.guild.id, previous.requester_id, previous.requester_name
            )
        except ExtractorError as exc:
            logger.warning("Autoplay failed guild=%s: %s", self.guild.id, exc)
            return
        for candidate in candidates:
            if (
                candidate.webpage_url == previous.webpage_url
                or candidate.webpage_url in self._autoplay_history
            ):
                continue
            self._autoplay_history.add(candidate.webpage_url)
            try:
                self.queue.add(candidate)
            except QueueError:
                return
            break

    async def _record_history(self, track: Track) -> None:
        if self.history is None:
            return
        try:
            await self.history.record(
                self.guild.id, track.requester_id, track.history_values(), self.position
            )
        except Exception:
            logger.exception("Could not write history guild=%s", self.guild.id)

    async def _update_panel(self, stopped: bool = False) -> None:
        if self.panel_updater is not None:
            try:
                await self.panel_updater(self, stopped)
            except (discord.HTTPException, discord.Forbidden, discord.NotFound):
                self.panel_message = None
            except Exception:
                logger.exception("Panel update failed guild=%s", self.guild.id)

    async def _safe_send(self, message: str) -> None:
        try:
            await self.text_channel.send(message)  # type: ignore[union-attr]
        except (discord.HTTPException, discord.Forbidden, discord.NotFound):
            logger.warning("Could not send player message guild=%s", self.guild.id)

    async def _idle_watchdog(self) -> None:
        try:
            while True:
                await asyncio.sleep(30)
                if self.voice_client is None or not self.voice_client.is_connected():
                    continue
                channel = self.voice_client.channel
                humans = [member for member in channel.members if not member.bot]
                if humans or self.queue or self.current:
                    continue
                await asyncio.sleep(self.auto_disconnect_timeout)
                if self.voice_client and self.voice_client.is_connected():
                    humans = [
                        member for member in self.voice_client.channel.members if not member.bot
                    ]
                    if not humans and not self.queue and self.current is None:
                        await self.leave()
                        return
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Idle watchdog failed guild=%s", self.guild.id)

    async def close(self) -> None:
        self._watchdog.cancel()
        await self.stop(disconnect=True)
