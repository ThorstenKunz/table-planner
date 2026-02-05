# Table Planner Bot

DISCLAIMER: This is merely an experiment to, finally, get myself into Python. So the code quality might
be bad, buggy and outrigth scary!

A Discord bot to organize game tables for tabletop RPGs, miniatures, and similar sessions. GMs can post tables via slash commands, players can join via buttons, and all sign-ups persist across restarts.

## Features

- Slash commands for creating and managing tables.
- Interactive join/leave buttons with persistent state.
- JSON storage with automatic recovery on restart.
- Rate limits to prevent command spam.
- Works well on headless Linux servers (e.g., Raspberry Pi).

## Quick Start

1. Create a .env file with your bot token:

   DISCORD_TOKEN=your-token-here

2. Install dependencies and run:

   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python main.py

## Docker

Build and run:

- docker build -t table-planner:latest .
- docker run --rm -e DISCORD_TOKEN=your-token-here -v $(pwd)/data:/app/data table-planner:latest

The Docker build runs tests in a first stage; the runtime image is built only if tests pass.

## Commands

- /create-table
  Opens a modal to create a new table in the current channel.

- /show-tables
  Shows all active tables. In a server channel, it shows only tables in that channel. In DMs, it shows only tables you can access.

- /list-tables
  Posts a compact list of all active tables in the current channel. In DMs, it shows only tables you can access.

- /my-tables
  Shows tables you run or play in. In DMs, it lists your tables for a single server only.

- /archive-table
  Archive one of your tables (or any table you can moderate via Manage Messages).

- /edit-table
  Edit one of your tables (or any table you can moderate via Manage Messages).

## Configuration

Configuration is stored in data/config.json. The bot reads it on startup.

Example:

```json
{
  "list_tables": {
    "column_widths": {
      "system": 20,
      "schedule": 24,
      "gm": 24,
      "players": 10
    }
  },
  "my_tables": {
    "column_widths": {
      "system": 20,
      "schedule": 24,
      "gm": 24,
      "players": 10,
      "status": 10
    }
  },
  "rate_limits": {
    "user_command_limit": 3,
    "user_command_window_seconds": 10,
    "guild_command_limit": 12,
    "guild_command_window_seconds": 10
  }
}
```

Notes:
- Column widths affect the monospace table output for /list-tables and /my-tables.
- Rate limits apply to /show-tables, /list-tables, and /my-tables.

## Data Storage

Active and archived tables are stored in:
- data/tables_active.json
- data/tables_archived.json

## Tests

Run tests locally:

- pytest

## Permissions

Required bot permissions (recommended):
- Send Messages
- Embed Links
- Read Message History
- Use Application Commands

If the bot cannot post or edit messages in a channel, it logs a warning and skips the update.
