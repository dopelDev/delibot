# test/test_bot_main.py

from app.bot.bot_main import create_bot


def test_create_bot():
    bot, TOKEN = create_bot()
    assert bot is not None
    assert isinstance(TOKEN, str)
