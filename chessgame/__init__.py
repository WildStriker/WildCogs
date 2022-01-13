"""chess cog init"""
from .chessgame import ChessGame


def setup(bot):
    """add cog to bot collection"""
    cog = ChessGame()
    bot.add_cog(cog)
    cog.create_init_task()
