from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class GuildSettings(Base):
    __tablename__ = "guild_settings"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dj_role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    default_volume: Mapped[int] = mapped_column(Integer, default=65)
    autoplay: Mapped[bool] = mapped_column(Boolean, default=False)
    max_queue_size: Mapped[int] = mapped_column(Integer, default=100)
    announce_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    auto_disconnect_timeout: Mapped[int] = mapped_column(Integer, default=300)
    allow_volume_100: Mapped[bool] = mapped_column(Boolean, default=False)
    permissions: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
    )


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    preferences: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
    )


class Playlist(Base):
    __tablename__ = "playlists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(100))
    visibility: Mapped[str] = mapped_column(String(10), default="private")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )
    tracks: Mapped[list[PlaylistTrack]] = relationship(
        back_populates="playlist", cascade="all, delete-orphan", order_by="PlaylistTrack.position"
    )
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_playlist_owner_name"),)


class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    playlist_id: Mapped[str] = mapped_column(
        ForeignKey("playlists.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(500))
    artist: Mapped[str] = mapped_column(String(300), default="Unknown")
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    thumbnail: Mapped[str | None] = mapped_column(Text, nullable=True)
    playlist: Mapped[Playlist] = relationship(back_populates="tracks")
    __table_args__ = (UniqueConstraint("playlist_id", "url", name="uq_playlist_track_url"),)


class Favorite(Base):
    __tablename__ = "favorites"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_url: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    artist: Mapped[str] = mapped_column(String(300), default="Unknown")
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    thumbnail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )


class History(Base):
    __tablename__ = "history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    source_url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(500))
    artist: Mapped[str] = mapped_column(String(300), default="Unknown")
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_played: Mapped[float] = mapped_column(Float, default=0)
    played_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), index=True
    )
