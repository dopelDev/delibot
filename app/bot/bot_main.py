# app/bot/bot_main.py
"""
Entrypoint and bot wiring for Delibot.

This module creates, configures, and runs a discord.py bot. It:
- Loads environment variables from <ROOT_PATH>/discord.env (without overriding existing env).
- Reads token, guild ID, and command prefix from the environment.
- Sets up Discord intents and loads core extensions in `setup_hook` (discord.py 2.x).
- Starts the bot with a clean shutdown path.
"""

from __future__ import annotations  # Enables postponed evaluation of annotations

import os
import sys
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from app.utils.logger import ROOT_PATH, get_logger

# Carga variables de entorno desde discord.env temprano (no pisa env existentes)
load_dotenv(dotenv_path=ROOT_PATH / "discord.env", override=False)
LOG = get_logger(__name__)


# ---- Helper pequeño (fuera de create_bot)
async def _resolve_guild(bot: commands.Bot, guild_id: int) -> discord.Guild | None:
    """Try cache first; if missing, fetch via API. Log causas conocidas."""
    guild = bot.get_guild(guild_id)
    if guild:
        return guild
    try:
        return await bot.fetch_guild(guild_id)
    except discord.Forbidden:
        LOG.warning(
            "Forbidden to fetch guild %s; is the bot in that server?", guild_id)
    except discord.NotFound:
        LOG.warning("Guild %s not found; is the ID correct?", guild_id)
    except discord.HTTPException as e:
        LOG.warning("Error fetching guild %s: %s", guild_id, e)
    return None


# --- Bot subclass -------------------------------------------------------------


class Delibot(commands.Bot):
    """
    Discord bot subclass that centralizes startup behavior.

    `setup_hook` runs before connecting to the gateway in discord.py 2.x
    and is the right place to load extensions and schedule background tasks.
    """

    async def setup_hook(self) -> None:
        """
        Asynchronously load core extensions and perform startup tasks.

        Notes:
            - Uses fully qualified module path `app.bot.commands.basic_commands`.
        """
        # Carga la extensión con los comandos básicos (!ping, etc.)
        await self.load_extension("app.bot.commands.basic_commands")
        LOG.info("✅ basic_commands extension loaded")
        LOG.debug("Loaded commands: %s", [
                  c.qualified_name for c in self.commands])


# --- Factory & runner ---------------------------------------------------------

def create_bot() -> tuple[commands.Bot, str]:
    """
    Create and configure the Discord bot instance.

    Reads:
        - DISCORD_TOKEN: Bot token.
        - DISCORD_GUILD_ID: Optional guild ID to log/verify on ready.
        - PREFIX: Command prefix (defaults to '!').

    Returns:
        tuple[commands.Bot, str]: A `(bot, token)` pair.
    """
    # Asegura que ROOT_PATH esté en sys.path para imports paquetizados
    if str(ROOT_PATH) not in sys.path:
        sys.path.insert(0, str(ROOT_PATH))

    # Lee configuración del entorno usando os.getenv
    token = os.getenv("DISCORD_TOKEN", "").strip()
    prefix = os.getenv("PREFIX", "!").strip()
    guild_id_str = os.getenv("DISCORD_GUILD_ID", "").strip()
    guild_id = int(guild_id_str) if guild_id_str.isdigit() else None

    # Configura intents (message_content necesario para comandos con prefijo)
    intents = discord.Intents.default()
    intents.message_content = True  # Requerido en v2 para prefijo
    intents.members = True          # Útil si luego se usan datos de miembros

    # Instancia del bot con prefijo configurado
    bot = Delibot(command_prefix=prefix, intents=intents)

    @bot.event
    async def on_ready() -> None:
        LOG.info("Connected as %s", bot.user)

        gid = guild_id
        if not gid:
            # No hay GUILD_ID configurado; nada más que hacer.
            return

        guild = await _resolve_guild(bot, gid)
        # Diagnóstico: en qué canales de texto puedo leer/enviar
        for ch in guild.text_channels:
            perms = ch.permissions_for(guild.me)
            LOG.info(
                "[%s] view=%s, read_history=%s, send=%s",
                ch.name, perms.view_channel, perms.read_message_history, perms.send_messages
            )
        if guild:
            LOG.info("Connected in server: %s (ID: %s)", guild.name, guild.id)
            return

        LOG.warning(
            "Configured DISCORD_GUILD_ID=%s but guild could not be resolved", gid)

    return bot, token


def run_bot() -> None:
    """
    Start the Discord bot and manage its lifecycle.

    Validates the presence of `DISCORD_TOKEN`, starts the client, and
    guarantees a graceful shutdown even if startup fails or is cancelled.
    """
    # Crea bot y obtiene token desde el entorno
    bot, token = create_bot()

    # Falla rápido si falta el token
    if not token:
        LOG.error("DISCORD_TOKEN no está definido en el entorno/discord.env")
        raise SystemExit(1)

    async def runner() -> None:
        """Coroutine wrapper that starts the bot and ensures clean teardown."""
        try:
            # Inicia la conexión al gateway de Discord
            await bot.start(token)
        finally:
            # Asegura cierre limpio si `start()` falla o se cancela
            if not bot.is_closed():
                await bot.close()

    # Ejecuta el runner en el event loop principal
    asyncio.run(runner())


if __name__ == "__main__":
    # Permite ejecutar el módulo directamente: `python app/bot/bot_main.py`
    run_bot()
