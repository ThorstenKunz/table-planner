import logging
import os

from dotenv import load_dotenv

from table_planner import TablePlannerBot, setup_commands

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    logging.getLogger(__name__).error("FATAL: DISCORD_TOKEN not found in .env file. Please check your configuration.")
    raise SystemExit(1)

bot = TablePlannerBot()


@bot.event
async def on_ready() -> None:
    if bot.user:
        logging.getLogger(__name__).info("✅ Logged in as %s (ID: %s)", bot.user, bot.user.id)
    else:
        logging.getLogger(__name__).error("on_ready event triggered but bot.user is None.")


setup_commands(bot)

bot.run(TOKEN)
