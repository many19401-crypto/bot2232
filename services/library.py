from __future__ import annotations

from database.repositories.library import FavoriteRepository, HistoryRepository


class LibraryService:
    def __init__(self, favorites: FavoriteRepository, history: HistoryRepository):
        self.favorites = favorites
        self.history = history
