"""Configuration helpers for the table planner bot."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

DATA_DIR = "data"
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

_DEFAULT_LIST_TABLE_WIDTHS: Dict[str, int] = {
    "system": 20,
    "schedule": 24,
    "gm": 24,
    "players": 10,
}

_DEFAULT_MY_TABLE_WIDTHS: Dict[str, int] = {
    "system": 20,
    "schedule": 24,
    "gm": 24,
    "players": 10,
    "status": 10,
}

_DEFAULT_USER_COMMAND_LIMIT = 3
_DEFAULT_USER_COMMAND_WINDOW_SECONDS = 10
_DEFAULT_GUILD_COMMAND_LIMIT = 12
_DEFAULT_GUILD_COMMAND_WINDOW_SECONDS = 10

_column_widths_cache: Dict[str, int] | None = None
_my_tables_widths_cache: Dict[str, int] | None = None
_user_command_rate_limit_cache: tuple[int, int] | None = None
_guild_command_rate_limit_cache: tuple[int, int] | None = None


def _load_config() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_FILE):
        return {}

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict):
                return data
            logger.warning("Config file %s does not contain a dictionary.", CONFIG_FILE)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not load config from %s: %s", CONFIG_FILE, exc)
    return {}


def get_list_table_column_widths() -> Dict[str, int]:
    """Return column widths for the /list-tables output."""
    global _column_widths_cache
    if _column_widths_cache is not None:
        return _column_widths_cache

    config = _load_config()
    result = dict(_DEFAULT_LIST_TABLE_WIDTHS)

    list_tables_cfg = config.get("list_tables")
    if isinstance(list_tables_cfg, dict):
        widths = list_tables_cfg.get("column_widths")
        if isinstance(widths, dict):
            for key, default_value in _DEFAULT_LIST_TABLE_WIDTHS.items():
                override = widths.get(key)
                if isinstance(override, int) and override > 0:
                    result[key] = override

    _column_widths_cache = result
    return result


def get_my_table_column_widths() -> Dict[str, int]:
    """Return column widths for the /my-tables output."""
    global _my_tables_widths_cache
    if _my_tables_widths_cache is not None:
        return _my_tables_widths_cache

    config = _load_config()
    result = dict(_DEFAULT_MY_TABLE_WIDTHS)

    my_tables_cfg = config.get("my_tables")
    if isinstance(my_tables_cfg, dict):
        widths = my_tables_cfg.get("column_widths")
        if isinstance(widths, dict):
            for key, default_value in _DEFAULT_MY_TABLE_WIDTHS.items():
                override = widths.get(key)
                if isinstance(override, int) and override > 0:
                    result[key] = override

    _my_tables_widths_cache = result
    return result


def get_user_command_rate_limit() -> tuple[int, int]:
    """Return per-user rate limit as (max_commands, window_seconds)."""
    global _user_command_rate_limit_cache
    if _user_command_rate_limit_cache is not None:
        return _user_command_rate_limit_cache

    config = _load_config()
    rate_cfg = config.get("rate_limits")
    max_commands = _DEFAULT_USER_COMMAND_LIMIT
    window_seconds = _DEFAULT_USER_COMMAND_WINDOW_SECONDS
    if isinstance(rate_cfg, dict):
        candidate_limit = rate_cfg.get("user_command_limit")
        candidate_window = rate_cfg.get("user_command_window_seconds")
        if isinstance(candidate_limit, int) and candidate_limit > 0:
            max_commands = candidate_limit
        if isinstance(candidate_window, int) and candidate_window > 0:
            window_seconds = candidate_window

    _user_command_rate_limit_cache = (max_commands, window_seconds)
    return _user_command_rate_limit_cache


def get_guild_command_rate_limit() -> tuple[int, int]:
    """Return per-guild rate limit as (max_commands, window_seconds)."""
    global _guild_command_rate_limit_cache
    if _guild_command_rate_limit_cache is not None:
        return _guild_command_rate_limit_cache

    config = _load_config()
    rate_cfg = config.get("rate_limits")
    max_commands = _DEFAULT_GUILD_COMMAND_LIMIT
    window_seconds = _DEFAULT_GUILD_COMMAND_WINDOW_SECONDS
    if isinstance(rate_cfg, dict):
        candidate_limit = rate_cfg.get("guild_command_limit")
        candidate_window = rate_cfg.get("guild_command_window_seconds")
        if isinstance(candidate_limit, int) and candidate_limit > 0:
            max_commands = candidate_limit
        if isinstance(candidate_window, int) and candidate_window > 0:
            window_seconds = candidate_window

    _guild_command_rate_limit_cache = (max_commands, window_seconds)
    return _guild_command_rate_limit_cache

