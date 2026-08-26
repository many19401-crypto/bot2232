from __future__ import annotations

import logging
import sys


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )
    logging.getLogger("discord.http").setLevel(
        max(logging.WARNING, getattr(logging, level.upper()))
    )
