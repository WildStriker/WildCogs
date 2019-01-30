'''chess cog init'''
from .chessgame import ChessGame


def setup(bot):
    '''add cog to bot collection'''
    bot.add_cog(ChessGame())
