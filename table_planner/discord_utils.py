"""Discord interaction helper utilities."""

from __future__ import annotations

import logging
from typing import Any

import discord

logger = logging.getLogger(__name__)


async def safe_response_send(
    interaction: discord.Interaction,
    content: str,
    **kwargs: Any,
) -> bool:
    try:
        await interaction.response.send_message(content, **kwargs)
        return True
    except discord.Forbidden:
        logger.warning(
            "Missing permission to respond in channel %s (%s).",
            getattr(interaction.channel, "name", "unknown"),
            getattr(interaction.channel, "id", "unknown"),
        )
    except discord.HTTPException as exc:
        logger.error(
            "Failed to send interaction response in channel %s (%s): %s",
            getattr(interaction.channel, "name", "unknown"),
            getattr(interaction.channel, "id", "unknown"),
            exc,
        )
    return False


async def safe_followup_send(
    interaction: discord.Interaction,
    content: str,
    **kwargs: Any,
) -> bool:
    try:
        await interaction.followup.send(content, **kwargs)
        return True
    except discord.Forbidden:
        logger.warning(
            "Missing permission to send followup in channel %s (%s).",
            getattr(interaction.channel, "name", "unknown"),
            getattr(interaction.channel, "id", "unknown"),
        )
    except discord.HTTPException as exc:
        logger.error(
            "Failed to send interaction followup in channel %s (%s): %s",
            getattr(interaction.channel, "name", "unknown"),
            getattr(interaction.channel, "id", "unknown"),
            exc,
        )
    return False
