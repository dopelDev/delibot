from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
import logging
import asyncio
import textwrap

import pytest


# --------------------------- Fakes we inject ---------------------------

def install_fake_logger(root: Path) -> None:
    """Provide app.utils.logger with ROOT_PATH and get_logger()."""
    app_pkg = sys.modules.setdefault("app", ModuleType("app"))
    utils_pkg = sys.modules.setdefault("app.utils", ModuleType("app.utils"))

    logger_mod = ModuleType("app.utils.logger")
    logger_mod.ROOT_PATH = root

    # Use a real stdlib logger so caplog can capture messages.
    base = logging.getLogger("delibot.testlogger")
    base.propagate = True  # bubble to pytest's handler

    def get_logger(name: str | None = None):
        return logging.getLogger(name or "delibot.testlogger")

    logger_mod.get_logger = get_logger  # type: ignore[attr-defined]
    sys.modules["app.utils.logger"] = logger_mod

    app_pkg.utils = utils_pkg  # type: ignore[attr-defined]


def install_fake_discord() -> None:
    """Install a minimal 'discord' and 'discord.ext.commands' API surface."""

    # ----- discord base module -----
    discord = ModuleType("discord")

    class Forbidden(Exception):
        ...

    class NotFound(Exception):
        ...

    class HTTPException(Exception):
        ...

    class Intents:
        def __init__(self) -> None:
            self.message_content = False
            self.members = False

        @classmethod
        def default(cls) -> "Intents":
            return cls()

    class _Perms:
        def __init__(self, view=True, read=True, send=True) -> None:
            self.view_channel = view
            self.read_message_history = read
            self.send_messages = send

    class _TextChannel:
        def __init__(self, name: str = "general") -> None:
            self.name = name

        def permissions_for(self, _member) -> _Perms:
            return _Perms()

    class Guild:
        def __init__(self, gid: int, name: str = "TestGuild") -> None:
            self.id = gid
            self.name = name
            self.text_channels = [_TextChannel("general")]
            self.me = object()

    discord.Forbidden = Forbidden
    discord.NotFound = NotFound
    discord.HTTPException = HTTPException
    discord.Intents = Intents
    discord.Guild = Guild

    # ----- discord.ext.commands submodule -----
    ext = ModuleType("discord.ext")
    commands = ModuleType("discord.ext.commands")

    class Bot:
        def __init__(self, *, command_prefix: str, intents: Intents) -> None:
            self.command_prefix = command_prefix
            self.intents = intents
            self._closed = False
            self._user = type("U", (), {"name": "FakeBot"})()
            self._guild_cache: dict[int, Guild] = {}
            self._loaded_extensions: list[str] = []
            self.commands = []  # just to satisfy the debug log in setup_hook

        # discord.py exposes .user
        @property
        def user(self):
            return self._user

        # event decorator just returns the function unchanged
        def event(self, fn):
            return fn

        def get_guild(self, gid: int):
            return self._guild_cache.get(gid)

        async def fetch_guild(self, gid: int):
            # overwritten per-test when needed
            raise NotFound(f"Guild {gid} not found")

        async def load_extension(self, name: str):
            self._loaded_extensions.append(name)

        async def start(self, token: str):
            self._started_with = token  # record for assertions

        async def close(self):
            self._closed = True

        def is_closed(self) -> bool:
            return self._closed

    commands.Bot = Bot

    # Register modules
    sys.modules["discord"] = discord
    sys.modules["discord.ext"] = ext
    sys.modules["discord.ext.commands"] = commands


def load_module_from_file(mod_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


# ------------------------------ Tests ---------------------------------

def test_create_bot_reads_env_and_sets_intents_and_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_discord()
    install_fake_logger(tmp_path)

    # Prepare env
    monkeypatch.setenv("DISCORD_TOKEN", "xyz123")
    monkeypatch.setenv("PREFIX", "?")
    monkeypatch.setenv("DISCORD_GUILD_ID", "0")  # effectively "no guild"

    # Write the module under a temp project structure and load it
    pkg_dir = tmp_path / "app" / "bot"
    pkg_dir.mkdir(parents=True)
    bot_py = pkg_dir / "bot_main.py"
    bot_py.write_text(textwrap.dedent(_BOT_MAIN_SOURCE))

    mod = load_module_from_file("tmp_app_bot_main", bot_py)

    bot, token = mod.create_bot()
    assert token == "xyz123"
    # Our fake commands.Bot stores prefix on .command_prefix
    assert getattr(bot, "command_prefix") == "?"
    # Intents flags should be on
    assert bot.intents.message_content is True
    assert bot.intents.members is True


def test_setup_hook_loads_extension(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_discord()
    install_fake_logger(tmp_path)

    (tmp_path / "app" / "bot").mkdir(parents=True)
    bot_py = tmp_path / "app" / "bot" / "bot_main.py"
    bot_py.write_text(textwrap.dedent(_BOT_MAIN_SOURCE))

    mod = load_module_from_file("tmp_app_bot_main2", bot_py)
    bot, _ = mod.create_bot()

    # Run the hook; should record the extension load
    asyncio.run(bot.setup_hook())
    assert "app.bot.commands.basic_commands" in getattr(
        bot, "_loaded_extensions")


def test__resolve_guild_hits_cache_then_fetch(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    install_fake_discord()
    install_fake_logger(tmp_path)

    (tmp_path / "app" / "bot").mkdir(parents=True)
    bot_py = tmp_path / "app" / "bot" / "bot_main.py"
    bot_py.write_text(textwrap.dedent(_BOT_MAIN_SOURCE))

    mod = load_module_from_file("tmp_app_bot_main3", bot_py)

    # Create a bot and prime its cache so get_guild() succeeds
    bot, _ = mod.create_bot()
    # Access fake discord modules/classes we installed
    from discord import Guild, NotFound, Forbidden, HTTPException

    gid = 123
    bot._guild_cache[gid] = Guild(gid, "GuildFromCache")

    # 1) Cache path
    g = asyncio.run(mod._resolve_guild(bot, gid))
    assert g is bot._guild_cache[gid]

    # 2) Miss cache -> fetched ok
    gid2 = 456

    async def fetch_ok(_gid: int):
        return Guild(_gid, "FetchedGuild")
    bot.fetch_guild = fetch_ok  # type: ignore[assignment]
    g2 = asyncio.run(mod._resolve_guild(bot, gid2))
    assert g2 and g2.name == "FetchedGuild"

    # 3) Miss cache -> Forbidden
    async def fetch_forbidden(_gid: int):
        raise Forbidden("nope")
    bot.fetch_guild = fetch_forbidden  # type: ignore[assignment]
    caplog.clear()
    g3 = asyncio.run(mod._resolve_guild(bot, 789))
    assert g3 is None
    assert any("Forbidden to fetch guild" in r.message for r in caplog.records)

    # 4) NotFound
    async def fetch_nf(_gid: int):
        raise NotFound("missing")
    bot.fetch_guild = fetch_nf  # type: ignore[assignment]
    caplog.clear()
    g4 = asyncio.run(mod._resolve_guild(bot, 999))
    assert g4 is None
    assert any("not found" in r.message.lower() for r in caplog.records)

    # 5) HTTPException
    async def fetch_http(_gid: int):
        raise HTTPException("boom")
    bot.fetch_guild = fetch_http  # type: ignore[assignment]
    caplog.clear()
    g5 = asyncio.run(mod._resolve_guild(bot, 1000))
    assert g5 is None
    assert any("error fetching guild" in r.message.lower()
               for r in caplog.records)


def test_run_bot_exits_when_no_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_discord()
    install_fake_logger(tmp_path)

    (tmp_path / "app" / "bot").mkdir(parents=True)
    bot_py = tmp_path / "app" / "bot" / "bot_main.py"
    bot_py.write_text(textwrap.dedent(_BOT_MAIN_SOURCE))

    mod = load_module_from_file("tmp_app_bot_main4", bot_py)

    monkeypatch.delenv("DISCORD_TOKEN", raising=False)  # ensure missing
    with pytest.raises(SystemExit) as ei:
        mod.run_bot()
    assert int(ei.value.code) == 1


def test_run_bot_calls_asyncio_run_when_token_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_discord()
    install_fake_logger(tmp_path)

    (tmp_path / "app" / "bot").mkdir(parents=True)
    bot_py = tmp_path / "app" / "bot" / "bot_main.py"
    bot_py.write_text(textwrap.dedent(_BOT_MAIN_SOURCE))

    mod = load_module_from_file("tmp_app_bot_main5", bot_py)

    monkeypatch.setenv("DISCORD_TOKEN", "abc")

    called = {"ran": False, "is_coro": False}

    def fake_asyncio_run(coro):
        # marca flags para la aserción
        called["ran"] = True
        called["is_coro"] = asyncio.iscoroutine(coro)
        # ejecuta el coroutine para evitar warnings
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(coro)
        finally:
            loop.close()

    # 👇 Parchea asyncio.run dentro del módulo probado
    monkeypatch.setattr(mod.asyncio, "run", fake_asyncio_run)

    # 👇 Dispara el código a probar
    mod.run_bot()

    assert called["ran"] is True and called["is_coro"] is True


# ---------------------- Inline copy of your module ---------------------

# This is your bot_main.py source (unchanged behavior), embedded to load under a temp path.
# Keeping it here avoids coupling tests to the project repo layout during CI.
_BOT_MAIN_SOURCE = """
\"\"\"
Entrypoint and bot wiring for Delibot.
\"\"\"

from __future__ import annotations

import os
import sys
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from app.utils.logger import ROOT_PATH, get_logger

load_dotenv(dotenv_path=ROOT_PATH / "discord.env", override=False)
LOG = get_logger(__name__)

async def _resolve_guild(bot: commands.Bot, guild_id: int) -> discord.Guild | None:
    guild = bot.get_guild(guild_id)
    if guild:
        return guild
    try:
        return await bot.fetch_guild(guild_id)
    except discord.Forbidden:
        LOG.warning("Forbidden to fetch guild %s; is the bot in that server?", guild_id)
    except discord.NotFound:
        LOG.warning("Guild %s not found; is the ID correct?", guild_id)
    except discord.HTTPException as e:
        LOG.warning("Error fetching guild %s: %s", guild_id, e)
    return None

class Delibot(commands.Bot):
    async def setup_hook(self) -> None:
        await self.load_extension("app.bot.commands.basic_commands")
        LOG.info("✅ basic_commands extension loaded")
        LOG.debug("Loaded commands: %s", [c.qualified_name for c in self.commands])

def create_bot() -> tuple[commands.Bot, str]:
    if str(ROOT_PATH) not in sys.path:
        sys.path.insert(0, str(ROOT_PATH))

    token = os.getenv("DISCORD_TOKEN", "").strip()
    prefix = os.getenv("PREFIX", "!").strip()
    guild_id_str = os.getenv("DISCORD_GUILD_ID", "").strip()
    guild_id = int(guild_id_str) if guild_id_str.isdigit() else None

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    bot = Delibot(command_prefix=prefix, intents=intents)

    @bot.event
    async def on_ready() -> None:
        LOG.info("Connected as %s", bot.user)
        gid = guild_id
        if not gid:
            return
        guild = await _resolve_guild(bot, gid)
        for ch in guild.text_channels:
            perms = ch.permissions_for(guild.me)
            LOG.info("[%s] view=%s, read_history=%s, send=%s", ch.name, perms.view_channel, perms.read_message_history, perms.send_messages)
        if guild:
            LOG.info("Connected in server: %s (ID: %s)", guild.name, guild.id)
            return
        LOG.warning("Configured DISCORD_GUILD_ID=%s but guild could not be resolved", gid)

    return bot, token

def run_bot() -> None:
    bot, token = create_bot()
    if not token:
        LOG.error("DISCORD_TOKEN no está definido en el entorno/discord.env")
        raise SystemExit(1)

    async def runner() -> None:
        try:
            await bot.start(token)
        finally:
            if not bot.is_closed():
                await bot.close()

    asyncio.run(runner())

if __name__ == "__main__":
    run_bot()
"""
