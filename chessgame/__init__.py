"""chess cog init"""
import discord

from .chessgame import ChessGame, StartUp


async def setup(bot):
    """add cog to bot collection"""
    cog = ChessGame()
    if discord.version_info.major >= 2:
        await bot.add_cog(cog)
    else:
        bot.add_cog(cog)
    cog.startup = StartUp()
    cog.startup.create_init_task(cog)
