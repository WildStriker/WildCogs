"""module contains helper functions used across other modules"""

import io
from typing import Dict, Union

import discord
import jsonpickle
from redbot.core import commands

from .constants import DEFAULT_ELO
from .game import Game

# type hints
Games = Dict[str, Game]


class Util:
    """handles ChessGame's shared functionality"""
    async def _get_games(self, channel) -> Games:
        config_games = await self._config.channel(channel).games()
        if not config_games:
            return None

        games = {}
        for game_name in config_games:
            game = jsonpickle.decode(config_games[game_name])
            games[game_name] = game

        return games

    async def _get_game(self, channel, game_name: str) -> Game:
        game_json = await self._config.channel(channel).games.get_raw(game_name)
        game = jsonpickle.decode(game_json)
        return game

    async def _set_game(self, channel, game_name: str, game: Game):
        game_json = jsonpickle.encode(game)
        await self._config.channel(channel).games.set_raw(game_name, value=game_json)

    async def _increment_score(self,
                               guild,
                               player_id: Union[int, str],
                               elo: int,
                               wins: int,
                               losses: int,
                               ties: int):
        player_id = str(player_id)
        async with self._config.guild(guild).scoreboard() as scoreboard:
            if player_id in scoreboard:
                player_score = scoreboard[player_id]
                player_score["elo"] += elo
                player_score["wins"] += wins
                player_score["losses"] += losses
                player_score["ties"] += ties
            else:
                player_score = {
                    "elo": DEFAULT_ELO + elo,
                    "wins": wins,
                    "losses": losses,
                    "ties": ties
                }

            scoreboard[player_id] = player_score

    async def _start_game(self, ctx: commands.Context,
                          player_black: discord.Member, player_white: discord.Member,
                          game_name: str = None, game_type: str = None):
        # get games config
        games = await self._config.channel(ctx.channel).games()
        if not games:
            games = {}

        # init game_name if not provided
        if not game_name:
            game_name = 'game'

        # make game_name unique if already exists
        count = 0
        suffix = ''
        while game_name + suffix in games:
            count += 1
            suffix = f'{count}'

        game_name += suffix

        embed: discord.Embed = discord.Embed()
        embed.title = "Chess"
        embed.description = f"Game: {game_name}"

        try:
            game = Game(player_black.id, player_white.id, game_type)
        except ValueError:
            embed.add_field(name='Invalid Game Type:', value=game_type)
            await ctx.send(embed=embed)
            return

        await self._set_game(ctx.channel, game_name, game)

        embed: discord.Embed = discord.Embed()
        embed.title = "Chess"
        embed.description = f"Game: {game_name}"
        embed.add_field(name="Type:", value=game.type, inline=False)

        embed.add_field(name="New Game",
                        value=f"<@{player_white.id}>'s (White's) turn is first",
                        inline=False)

        await self._display_board(ctx, f"<@{player_white.id}>", embed, game)

    async def _display_board(self,
                             ctx: commands.Context,
                             content: str,
                             embed: discord.Embed,
                             game: Game):
        """displays the game board"""
        board_image = io.BytesIO(game.get_board_image())
        embed.set_image(url="attachment://board.png")
        await ctx.send(content, embed=embed, file=discord.File(board_image, 'board.png'))
