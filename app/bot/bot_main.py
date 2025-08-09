# app/bot/bot_main.py
from __future__ import annotations

import os
import sys
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

# ROOT_PATH global y logger central
from app.utils.logger import ROOT_PATH, get_logger
# Cargar variables de entorno temprano (idempotente; no pisa env existentes)
load_dotenv(dotenv_path=ROOT_PATH / "discord.env", override=False)

LOG = get_logger(__name__)


def create_bot() -> tuple[commands.Bot, str]:
    """
    Creates and configures the Discord bot instance.

    Loads environment variables from <ROOT_PATH>/discord.env,
    sets up Discord intents, creates the bot with the configured command prefix,
    and attaches basic startup hooks.

    Returns:
        (bot, TOKEN)
    """
    # ⚠️ Mejor ejecutar como paquete: `python -m app.bot.bot_main`
    # y evitar sys.path hacks; si necesitas mantenerlo, déjalo.
    if str(ROOT_PATH) not in sys.path:
        sys.path.insert(0, str(ROOT_PATH))

    TOKEN = os.getenv("DISCORD_TOKEN")
    GUILD_ID = os.getenv("DISCORD_GUILD_ID")
    PREFIX = os.getenv("PREFIX", "!")

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    bot = commands.Bot(command_prefix=PREFIX, intents=intents)

    @bot.event
    async def on_ready():
        LOG.info("Connected as %s", bot.user)
        if GUILD_ID:
            guild = bot.get_guild(int(GUILD_ID))
            if guild:
                LOG.info("Connected in server: %s (ID: %s)",
                         guild.name, guild.id)

    # Cargar extensiones en setup_hook (patrón recomendado en discord.py 2.x)
    @bot.event
    async def setup_hook() -> None:
        await bot.load_extension("app.bot.commands.basic_commands")
        LOG.info("✅ basic_commands extension loaded")
        LOG.debug("Loaded commands: %s", [cmd.name for cmd in bot.commands])

    return bot, TOKEN


def run_bot() -> None:
    """Entry point to start the Discord bot."""
    bot, token = create_bot()
    if not token:
        LOG.error("DISCORD_TOKEN no está definido en el entorno/discord.env")
        raise SystemExit(1)

    async def runner():
        try:
            await bot.start(token)
        finally:
            # Cierre limpio si falla start() o se cancela
            if bot.is_closed():
                return
            await bot.close()

    asyncio.run(runner())


if __name__ == "__main__":
    run_bot()
