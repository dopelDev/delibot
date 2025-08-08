# basic_commands.py

from discord.ext import commands


class BasicCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        await ctx.send('¡Pong!')

# Cargar la extensión


async def setup(bot):
    await bot.add_cog(BasicCommands(bot))
