from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from database.models import Playlist, PlaylistTrack


class PlaylistRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession], max_tracks: int = 500):
        self.factory = factory
        self.max_tracks = max_tracks

    async def create(self, owner_id: int, name: str, visibility: str = "private") -> Playlist:
        if visibility not in {"private", "public"}:
            raise ValueError("Visibility must be private or public")
        async with self.factory() as session:
            playlist = Playlist(owner_id=owner_id, name=name.strip(), visibility=visibility)
            session.add(playlist)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ValueError("A playlist with this name already exists") from exc
            await session.refresh(playlist)
            return playlist

    async def get(self, playlist_id: str, owner_id: int | None = None) -> Playlist | None:
        async with self.factory() as session:
            query = (
                select(Playlist)
                .options(selectinload(Playlist.tracks))
                .where(Playlist.id == playlist_id)
            )
            if owner_id is not None:
                query = query.where(
                    (Playlist.owner_id == owner_id) | (Playlist.visibility == "public")
                )
            return await session.scalar(query)

    async def by_owner(self, owner_id: int) -> list[Playlist]:
        async with self.factory() as session:
            return list(
                (
                    await session.scalars(
                        select(Playlist)
                        .where(Playlist.owner_id == owner_id)
                        .order_by(Playlist.name)
                    )
                ).all()
            )

    async def add_track(
        self, playlist_id: str, owner_id: int, values: dict[str, object]
    ) -> PlaylistTrack:
        async with self.factory() as session:
            playlist = await session.scalar(
                select(Playlist)
                .where(Playlist.id == playlist_id, Playlist.owner_id == owner_id)
                .with_for_update()
            )
            if playlist is None:
                raise ValueError("Playlist not found or you are not its owner")
            count = await session.scalar(
                select(func.count())
                .select_from(PlaylistTrack)
                .where(PlaylistTrack.playlist_id == playlist_id)
            )
            if (count or 0) >= self.max_tracks:
                raise ValueError("Playlist has reached its track limit")
            duplicate = await session.scalar(
                select(PlaylistTrack).where(
                    PlaylistTrack.playlist_id == playlist_id, PlaylistTrack.url == values["url"]
                )
            )
            if duplicate is not None:
                raise ValueError("This track is already in the playlist")
            position = int(count or 0) + 1
            track = PlaylistTrack(playlist_id=playlist_id, position=position, **values)
            session.add(track)
            await session.commit()
            await session.refresh(track)
            return track

    async def remove_track(self, playlist_id: str, owner_id: int, position: int) -> bool:
        async with self.factory() as session:
            playlist = await session.scalar(
                select(Playlist).where(Playlist.id == playlist_id, Playlist.owner_id == owner_id)
            )
            if playlist is None:
                raise ValueError("Playlist not found or you are not its owner")
            track = await session.scalar(
                select(PlaylistTrack).where(
                    PlaylistTrack.playlist_id == playlist_id, PlaylistTrack.position == position
                )
            )
            if track is None:
                return False
            await session.delete(track)
            await session.flush()
            tracks = list(
                (
                    await session.scalars(
                        select(PlaylistTrack)
                        .where(PlaylistTrack.playlist_id == playlist_id)
                        .order_by(PlaylistTrack.position)
                    )
                ).all()
            )
            for index, item in enumerate(tracks, 1):
                item.position = index
            await session.commit()
            return True

    async def delete(self, playlist_id: str, owner_id: int) -> bool:
        async with self.factory() as session:
            result = await session.execute(
                delete(Playlist).where(Playlist.id == playlist_id, Playlist.owner_id == owner_id)
            )
            await session.commit()
            return result.rowcount > 0
