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
    if interaction.response.is_done():
        return await safe_followup_send(interaction, content, **kwargs)

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


async def safe_response_defer(interaction: discord.Interaction) -> bool:
    """Acknowledge an interaction before doing potentially slow work."""
    if interaction.response.is_done():
        return True

    try:
        await interaction.response.defer()
        return True
    except discord.InteractionResponded:
        return True
    except discord.Forbidden:
        logger.warning(
            "Missing permission to defer interaction in channel %s (%s).",
            getattr(interaction.channel, "name", "unknown"),
            getattr(interaction.channel, "id", "unknown"),
        )
    except discord.HTTPException as exc:
        logger.error(
            "Failed to defer interaction in channel %s (%s): %s",
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
