# app/main.py

"""
Main entrypoint for Delibot Discord bot.

This script can be executed directly or as a module:
    python -m app.main
or
    python app/main.py

It initializes and runs the Discord bot using the run_bot() function
from app.bot.bot_main. You can extend this file for other administrative
tasks in the future.
"""

from app.bot.bot_main import run_bot
from app.utils.logger import get_logger

LOG = get_logger(__name__)


def main():
    """
    Runs the Delibot Discord bot.

    Calls the run_bot() function to initialize and start the bot.
    """
    LOG.info("Starting Delibot...")
    run_bot()


if __name__ == "__main__":
    main()
