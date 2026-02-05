# Project Context: Game Table Organizer Bot

## 1. Project Overview
This is a Discord Bot designed to organize all kinds of game table (Pen&Paper RPG, Miniatures, Table RPG, etc.) rounds.
**Core Functionality:**
- **GM Interface:** Slash commands (`/create-table`) to post new game listings (System, Date/Time, Max Players, Infos).
- **Player Interface:** Interactive Buttons ("Join", "Leave") attached to the game embed.
- **State Management:** The bot must track sign-ups persistently (JSON file). If the bot restarts, the buttons on old messages must still work.

## 2. Technical Architecture
- **Language:** Python 3.12+
- **Library:** `discord.py` (latest stable version).
- **Hosting:** Raspberry Pi 5 running Ubuntu 24.04 (Headless).
- **Development:** VS Code Remote - SSH.
- **Persistence Strategy:** JSON (local file).
    - *Constraint:* `discord.ui.View` must be persistent (`timeout=None`) and re-registered in `setup_hook` to listen for button clicks after a restart.
- **Testing:** `pytest` with `tests/` folder; Docker build runs tests in a first stage.

## 3. Environment Specifics
- **OS:** Ubuntu 24.04 (Linux). Use forward slashes `/` for paths.
- **Virtual Environment:** Located at `./.venv`.
- **Runtime Environment:** The bot will run dockerized.
- **Note:** Do not suggest GUI-based tools (like `tkinter`); this is a CLI/Headless environment.

## 4. Coding Standards & Patterns
- **Slash Commands:** Use `app_commands.CommandTree`.
- **Type Hinting:** Mandatory for all function arguments (e.g., `interaction: discord.Interaction`).
- **Async/Await:** Ensure all Discord interactions are awaited properly.
- **Error Handling:** Use `ephemeral=True` for user-facing errors (e.g., "Game is full").

## 5. Commands
- **/create-table:** Opens modal to create a table in the current server channel.
- **/show-tables:** Shows active tables. In server channels, only current channel; in DMs, only tables the user can access.
- **/list-tables:** Posts a compact list of active tables in the current channel.
- **/my-tables:** Shows tables where the user is GM/player/waiting. In DMs, lists a single server only.
- **/archive-table:** Archives a table owned by the user (or with Manage Messages permission).
- **/edit-table:** Edits a table owned by the user (or with Manage Messages permission).

## 6. Configuration
- Config file: `data/config.json`.
- Column width settings for `/list-tables` and `/my-tables`.
- Rate limits:
    - `rate_limits.user_command_limit`
    - `rate_limits.user_command_window_seconds`
    - `rate_limits.guild_command_limit`
    - `rate_limits.guild_command_window_seconds`

## 7. Code Structure
- Command handlers live in `table_planner/command_handlers/` (one file per command).
- Common helpers in `table_planner/command_handlers/utils.py`.
- Interaction send helpers in `table_planner/discord_utils.py`.
