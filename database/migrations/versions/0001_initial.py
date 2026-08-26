"""Initial persistent music platform schema."""

import sqlalchemy as sa

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guild_settings",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("dj_role_id", sa.BigInteger(), nullable=True),
        sa.Column("default_volume", sa.Integer(), nullable=False, server_default="65"),
        sa.Column("autoplay", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("max_queue_size", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("announce_channel_id", sa.BigInteger(), nullable=True),
        sa.Column("auto_disconnect_timeout", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("allow_volume_100", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("permissions", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("guild_id"),
    )
    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("preferences", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "playlists",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("visibility", sa.String(length=10), nullable=False, server_default="private"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "name", name="uq_playlist_owner_name"),
    )
    op.create_index("ix_playlists_owner_id", "playlists", ["owner_id"])
    op.create_table(
        "playlist_tracks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("playlist_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("artist", sa.String(length=300), nullable=False, server_default="Unknown"),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("thumbnail", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["playlist_id"], ["playlists.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("playlist_id", "url", name="uq_playlist_track_url"),
    )
    op.create_index("ix_playlist_tracks_playlist_id", "playlist_tracks", ["playlist_id"])
    op.create_table(
        "favorites",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("artist", sa.String(length=300), nullable=False, server_default="Unknown"),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("thumbnail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "source_url"),
    )
    op.create_table(
        "history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("artist", sa.String(length=300), nullable=False, server_default="Unknown"),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("duration_played", sa.Float(), nullable=False, server_default="0"),
        sa.Column("played_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_history_guild_id", "history", ["guild_id"])
    op.create_index("ix_history_user_id", "history", ["user_id"])
    op.create_index("ix_history_played_at", "history", ["played_at"])


def downgrade() -> None:
    op.drop_index("ix_history_played_at", table_name="history")
    op.drop_index("ix_history_user_id", table_name="history")
    op.drop_index("ix_history_guild_id", table_name="history")
    op.drop_table("history")
    op.drop_table("favorites")
    op.drop_index("ix_playlist_tracks_playlist_id", table_name="playlist_tracks")
    op.drop_table("playlist_tracks")
    op.drop_index("ix_playlists_owner_id", table_name="playlists")
    op.drop_table("playlists")
    op.drop_table("user_preferences")
    op.drop_table("guild_settings")
