# bot_main.py

import os
import sys
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from app.utils.path import get_project_root


def create_bot():
    """
    Creates and configures the Discord bot instance.

    Loads environment variables from the project root (using a marker file),
    sets up Discord intents, creates the bot with
    the configured command prefix, and attaches
    the on_ready event for basic logging when the bot connects.

    Returns:
        tuple: (bot, TOKEN)
            bot (commands.Bot): The initialized Discord bot instance.
            TOKEN (str): The Discord bot token loaded from environment
                         variables.
    """

    ROOT_DIR = get_project_root()
    sys.path.insert(0, str(ROOT_DIR))

    # import Environment Values
    ENV_PATH = ROOT_DIR / 'discord.env'
    load_dotenv(dotenv_path=ENV_PATH)

    TOKEN = os.getenv('DISCORD_TOKEN')
    GUILD_ID = os.getenv('DISCORD_GUILD_ID')
    PREFIX = os.getenv('PREFIX')

    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix=PREFIX, intents=intents)

    @bot.event
    async def on_ready():
        print(f'Connected as {bot.user}')
        if GUILD_ID:
            guild = bot.get_guild(int(GUILD_ID))
            print(f'Connected in server : {guild.name} (ID: {guild.id})')

    return bot, TOKEN


async def setup_extensions(bot):
    """
    Add extensions and basic_commands
    """
    await bot.load_extension('app.bot.commands.basic_commands')


def run_bot():
    """
    Entry point to start the Discord bot.

    This function creates the bot instance, loads all extensions, and runs the
    bot asynchronously using the loaded token. It is intended to be called
    either directly when running this module as the main program,
    or imported and called from another script.
    """
    bot, TOKEN = create_bot()

    async def runner():
        await setup_extensions(bot)
        await bot.start(TOKEN)
    asyncio.run(runner())


if __name__ == "__main__":
    run_bot()
