'''cog to play chess in discord'''
import io
import os
import tempfile
from typing import Dict

import chess
import chess.svg
import discord
from redbot.core import commands
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg


class Game:
    '''class used to hold state of a game'''

    def __init__(self, player_black, player_white):

        self._board = chess.Board()
        self._arrows = ()

        self._player_black = player_black
        self._player_white = player_white

    def get_board_text(self) -> str:
        '''returns the game board as text'''
        return str(self._board)

    def get_board_image(self) -> io.BytesIO:
        '''returns the game as an image

        can't embed svg, so convert to png first
        '''

        # write svg string to file
        svg_board = tempfile.NamedTemporaryFile(delete=False)
        svg_board.write(chess.svg.board(
            board=self._board, arrows=self._arrows).encode())
        svg_board.close()

        # convert to png
        drawing = svg2rlg(svg_board.name)
        png_board = tempfile.NamedTemporaryFile(delete=False)
        png_board.close()
        renderPM.drawToFile(drawing, png_board.name, fmt='PNG')

        # read to memory
        image_board: io.BytesIO = open(png_board.name, "rb").read()

        # remove tempfiles
        os.remove(svg_board.name)
        os.remove(png_board.name)

        return image_board

    def move_piece(self, move):
        '''move piece'''
        move: chess.Move = self._board.push_san(move)
        self._arrows = [(move.from_square, move.to_square)]

    @property
    def total_moves(self) -> int:
        '''total moves taken'''
        return len(self._board.move_stack)

    @property
    def turn(self):
        '''return which colour has the next turn'''
        return self._board.turn

    @property
    def player_white(self) -> discord.Member:
        '''returns the player assigned to white pieces'''
        return self._player_white

    @property
    def player_black(self) -> discord.Member:
        '''returns the player assigned to black pieces'''
        return self._player_black


class Chess(commands.Cog):
    '''Cog to Play chess!'''

    def __init__(self):
        super().__init__()

        self._games: Dict[str, Game] = {}

    @commands.group()
    async def chess(self, ctx: commands.Context):
        '''manage chess games'''

    @chess.group(name='start', autohelp=False)
    async def start_game(self, ctx: commands.Context,
                         other_player: discord.Member, game_name: str = None):
        '''sub command to start a new game'''

        player_black = ctx.author
        player_white = other_player

        # init game_name if not provided
        if not game_name:
            game_name = f'{player_black.name} vs {player_white.name}'

        # make game_name unique if already exists
        count = 0
        suffix = ''
        while game_name + suffix in self._games.keys():
            count += 1
            suffix = f' - {count}'

        game_name += suffix

        game = Game(player_black, player_white)
        self._games[game_name] = game

        embed: discord.Embed = discord.Embed()
        embed.title = "Chess"
        embed.description = f"Game: {game_name}"
        embed.add_field(name="New Game",
                        value=f"<@{player_white.id}>'s (White's) turn is first")

        await self._display_board(ctx, embed, game)

    async def _display_board(self, ctx: commands.Context, embed: discord.Embed, game: Game):
        '''displays the game board'''
        board_image = game.get_board_image()
        embed.set_image(url="attachment://board.png")
        await ctx.send(embed=embed, file=discord.File(board_image, 'board.png'))

    @chess.group(name='list', autohelp=False)
    async def list_games(self, ctx: commands.Context):
        '''list all available games'''
        embed: discord.Embed = discord.Embed()

        embed.title = f"Chess"
        embed.description = f"Chess Game List"

        if self._games:
            count = 0
            output = ''
            for game_name, game in self._games.items():
                count += 1
                output += f'\n** Game: #{count}** - __{game_name}__\n' \
                    f'```\tBlack: {game.player_black.name}\n' \
                    f'\tWhite: {game.player_white.name}\n' \
                    f'\tTotal Moves: {game.total_moves}```' \

            embed.add_field(name=f"List of current games:", value=output)
        else:
            embed.add_field(name=f"No Games Available",
                            value='You can start a new game with [p]chess start')

        await ctx.send(embed=embed)

    @chess.group(name='move', autohelp=False)
    async def move_piece(self, ctx: commands.Context, game_name: str, move: str):
        '''move the next game piece, using Standard Algebraic Notation'''

        embed: discord.Embed = discord.Embed()

        if game_name in self._games.keys():
            game = self._games[game_name]
        else:
            # this game doesn't exist
            embed.title = f"Chess"
            embed.description = f"Game: {game_name}"
            embed.add_field(name=f"Game does not exist",
                            value=f"This game doesn't appear to exist, please check the "
                            "game list to ensure you are entering it correctly")
            await ctx.send(embed=embed)
            return

        if game.turn == chess.WHITE:
            turn_color = 'White'
            player_turn = game.player_white
            player_next = game.player_black
        else:
            turn_color = 'Black'
            player_turn = game.player_black
            player_next = game.player_white

        if player_turn == ctx.author:
            # it is their turn
            game.move_piece(move)

            embed.title = f"Chess"
            embed.description = f"Game: {game_name}"

            embed.add_field(name=f"Move: {game.total_moves} - "
                            f"{player_turn.name}'s ({turn_color}'s) Turn",
                            value=f"<@{player_next.id}> you're up next!")

            await self._display_board(ctx, embed, game)
        elif player_next == ctx.author:
            # not their turn yet
            embed.title = f"Chess"
            embed.description = f"Game: {game_name}"
            embed.add_field(name=f"{player_next.name} - not your turn",
                            value=f"{player_next.name} it doesn't look like its your turn yet! "
                            f"<@{player_turn.id}> ({turn_color}) still needs to make a move "
                            "before you can.")
            await ctx.send(embed=embed)
        else:
            # not a player
            embed.title = f"Chess"
            embed.description = f"Game: {game_name}"
            embed.add_field(name=f"{ctx.author.name} - not a player",
                            value=f"{ctx.author.name} you are not part of this game!\n"
                            f"Only {game.player_black.name} (Black) and {game.player_white.name} ' \
                            '(White) are able to play in this game")
            await ctx.send(embed=embed)
