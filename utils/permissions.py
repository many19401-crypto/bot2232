from __future__ import annotations

import discord

from database.models import GuildSettings

_ACTION_DEFAULTS = {
    "skip": "everyone",
    "stop": "dj",
    "volume": "everyone",
    "clear": "dj",
    "disconnect": "dj",
    "autoplay": "dj",
    "move": "dj",
}


def is_dj(member: discord.Member, settings: GuildSettings) -> bool:
    return member.guild_permissions.administrator or bool(
        settings.dj_role_id and any(role.id == settings.dj_role_id for role in member.roles)
    )


def can(
    member: discord.Member, settings: GuildSettings, action: str, requester_id: int | None = None
) -> bool:
    if member.guild_permissions.administrator:
        return True
    mode = (settings.permissions or {}).get(action, _ACTION_DEFAULTS.get(action, "dj"))
    if mode == "everyone":
        return True
    if mode == "requester":
        return requester_id is not None and member.id == requester_id
    if mode == "admin":
        return member.guild_permissions.administrator
    return is_dj(member, settings)


def in_same_voice(
    member: discord.Member, player_channel: discord.VoiceChannel | discord.StageChannel | None
) -> bool:
    return (
        member.voice is not None
        and player_channel is not None
        and member.voice.channel.id == player_channel.id
    )
