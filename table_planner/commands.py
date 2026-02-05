"""Slash command registrations for the table planner bot."""

from __future__ import annotations

from typing import cast

import discord
from discord import app_commands

from .command_handlers.archive_table import register_archive_table
from .command_handlers.create_table import register_create_table
from .command_handlers.edit_table import register_edit_table
from .command_handlers.list_tables import register_list_tables
from .command_handlers.my_tables import register_my_tables
from .command_handlers.show_tables import register_show_tables


def setup_commands(bot: discord.Client) -> None:
    tree = cast(app_commands.CommandTree, getattr(bot, "tree"))
    register_create_table(tree, bot)
    register_show_tables(tree)
    register_list_tables(tree, bot)
    register_my_tables(tree, bot)
    register_archive_table(tree, bot)
    register_edit_table(tree, bot)
