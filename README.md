# Production Discord Music Bot

Полноценный асинхронный Discord music bot на Python 3.10+ (Python 3.13 рекомендуется), `discord.py 2.x`, PostgreSQL, Redis, yt-dlp и FFmpeg. Сессии воспроизведения изолированы по `guild_id`: очередь, блокировки, состояние voice и панель одного сервера никогда не используются другим сервером.

> **Ограничение источников.** yt-dlp и сайты-источники меняются независимо от бота. Бот не обходит DRM, paywall или приватный контент. Stream URL не сохраняется в PostgreSQL/Redis: он запрашивается заново непосредственно перед запуском FFmpeg.

## Возможности

- Slash commands `/play`, `/search`, `/pause`, `/resume`, `/skip`, `/stop`, `/queue`, `/nowplaying`, `/volume`, `/seek`, `/remove`, `/move`, `/clear`, `/shuffle`, `/loop`, `/join`, `/leave`, `/playnext`.
- `/play <текст>` показывает Select Menu на пять результатов. URL запускается напрямую, playlist URL добавляется с ограничением размера.
- Per-guild `MusicPlayer` с состояниями `IDLE`, `CONNECTING`, `PLAYING`, `PAUSED`, `STOPPING`, `RECONNECTING`, `ERROR`.
- Очередь с priority tracks, лимитом, move/remove/clear/shuffle, loop `off/track/queue`, pagination и кнопочной persistent control panel.
- Безопасное изменение громкости существующего `PCMVolumeTransformer`; `/seek` перестраивает только текущий stream.
- Автоповтор voice connection с backoff 2/5/10/30 секунд, обработка FFmpeg/extractor ошибок и переход к следующему треку.
- Autoplay с in-memory history anti-repeat, auto-disconnect если в канале остаётся только бот.
- PostgreSQL: настройки guild, preferences, playlists/tracks, favorites, listening history. Redis: metadata/search cache и будущие distributed rate limits; Redis outage не ломает playback.
- DJ role, administrator, requester/everyone modes для опасных действий.
- `/playlist create|add|remove|play|list|delete`, `/favorite add|remove`, `/favorites`, `/history`, `/recent`, `/play favorites`, `/settings`, `/status`.
- Не блокирует event loop: весь yt-dlp запускается через `asyncio.to_thread`; voice callbacks возвращаются в event loop потокобезопасно.

## Быстрый запуск Docker

```bash
cp .env.example .env
# задайте DISCORD_TOKEN в .env
docker compose up --build -d
```

Compose поднимает bot, PostgreSQL 17 и Redis 7, хранит PostgreSQL в volume, выполняет `alembic upgrade head` перед запуском бота и перезапускает контейнер.

## Локальная установка

Требуется Python 3.10+; для production рекомендуется Python 3.13+. Нужен FFmpeg с доступным executable и libopus/PyNaCl.

```bash
python3.13 -m venv .venv
. .venv/bin/activate
pip install -e ".[test]"
# Linux
sudo apt install ffmpeg
cp .env.example .env
# для локального запуска измените DATABASE_URL на вашу PostgreSQL и REDIS_URL
alembic upgrade head
python -m main
```

Для запуска без PostgreSQL можно использовать SQLite только для локального smoke-run, но production schema и миграции рассчитаны на PostgreSQL:

```env
DATABASE_URL=sqlite+aiosqlite:///./local.db
REDIS_URL=
```

В этом случае отдельно установите `aiosqlite`; приложение создаст SQLite schema автоматически.

## Discord application

1. В [Discord Developer Portal](https://discord.com/developers/applications) создайте Application и Bot.
2. Скопируйте токен только в `.env` (`DISCORD_TOKEN`), никогда не добавляйте его в Git.
3. В OAuth2 URL Generator выберите scopes `bot` и `applications.commands`.
4. Разрешения бота: `View Channels`, `Send Messages`, `Embed Links`, `Read Message History`, `Connect`, `Speak`, `Use Voice Activity`.
5. В `.env` задайте `DEV_GUILD_ID` для мгновенной регистрации slash commands в тестовом сервере. Без него команды регистрируются глобально и Discord может обновлять их до часа.
6. Если используется `/settings`, пользователю нужно `Manage Server`; bot role должна видеть и подключаться к voice channel.

## Конфигурация

Все настройки валидируются Pydantic Settings. Полный список находится в `.env.example`: database/Redis URL, лимиты queue/playlist, autoplay, idle timeout, retry count, cache TTL и путь к FFmpeg. В коде нет токенов, cookies или shell-команд из пользовательского ввода.

## Архитектура

```text
main.py
├── bot/client.py                 lifecycle, slash sync, global error boundary
├── cogs/                         thin Discord interaction handlers
├── views/                        owner/guild-scoped Select/Menu/Button UI
├── music/                        TrackQueue, MusicPlayer, voice, FFmpeg, yt-dlp
├── database/                     SQLAlchemy models, repositories, Alembic
├── services/                     Redis cache, rate limiter, library facade
├── config/                       Pydantic Settings
└── utils/                        permissions, embeds, timestamp/progress, logging
```

`MusicPlayer` owns an `asyncio.Lock`. `Skip`, `stop`, `seek` and audio completion are serialized per guild; callback from discord.py never mutates queue directly from its audio thread. `MusicManager.players` is the only guild registry.

## Миграции

```bash
DATABASE_URL=postgresql+asyncpg://... alembic upgrade head
DATABASE_URL=postgresql+asyncpg://... alembic downgrade -1
```

Миграции находятся в `database/migrations/versions`. `create_all` используется только для SQLite development convenience; PostgreSQL запускается через Alembic.

## Тесты и проверки

```bash
pip install -e ".[test]"
pytest -q
python -m compileall -q .
```

Unit tests покрывают bounded/priority queue, pagination, shuffle, timestamp validation, rate limits, loop cycling и concurrent skip serialization. Для интеграционного voice-теста используйте отдельный Discord test guild и доступный FFmpeg: реальные Discord gateway и внешние сайты намеренно не вызываются в unit suite.

## Troubleshooting

- **Slash commands не видны:** проверьте `applications.commands`, `DEV_GUILD_ID`, права приглашения и дождитесь global sync.
- **`ffmpeg was not found`:** установите FFmpeg или задайте абсолютный `FFMPEG_BIN`; Docker уже содержит FFmpeg.
- **yt-dlp не находит трек:** обновите `yt-dlp`, проверьте URL и доступность источника; unavailable track автоматически пропускается.
- **Не подключается voice:** проверьте `Connect/Speak`, voice channel permissions, UDP/network и наличие PyNaCl/libopus.
- **Database errors:** убедитесь, что PostgreSQL доступен и `alembic upgrade head` выполнен. Не используйте Redis как замену PostgreSQL.
- **Redis недоступен:** поиск продолжит работать без cache, но проверьте URL, если нужен cache/rate limit на нескольких replicas.
- **Два нажатия Skip:** per-guild lock и idempotent callback допускают только один переход; второй запрос получает корректный no-op.

## Безопасность и эксплуатация

Не добавляйте `.env`, cookies yt-dlp, stream URLs или логи с секретами в Git. FFmpeg запускается библиотекой с аргументами, не через shell. Ограничивайте bot permissions на уровне Discord и обновляйте зависимости. Для нескольких replicas voice-session ownership должен быть закреплён за одной replica на guild (Discord voice connection нельзя безопасно делить между процессами); Redis/PostgreSQL предназначены для shared data, не для управления одним FFmpeg.
