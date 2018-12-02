'''chess cog init'''
from .chess_game import Chess


def setup(bot):
    '''add cog to bot collection'''
    bot.add_cog(Chess(bot))
