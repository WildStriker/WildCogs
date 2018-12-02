'''cog to play chess in discord'''
import asyncio
import io
import os
import pickle
import tempfile
from typing import Dict

import chess
import chess.svg
import discord
from redbot.core import commands
from redbot.core.bot import Red
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg

SAVE_INTERVAL = 30


class Game:
    '''class used to hold state of a game'''

    def __init__(self, player_black_id, player_white_id):

        self._board = chess.Board()
        self._arrows = ()

        self._player_black_id = player_black_id
        self._player_white_id = player_white_id

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
    def player_white_id(self) -> discord.Member:
        '''returns the player assigned to white pieces'''
        return self._player_white_id

    @property
    def player_black_id(self) -> discord.Member:
        '''returns the player assigned to black pieces'''
        return self._player_black_id


# type hints
Games = Dict[str, Game]
Channels = Dict[str, Games]
Guilds = Dict[str, Channels]


class Chess(commands.Cog):
    '''Cog to Play chess!'''

    def __init__(self, bot: Red):
        super().__init__()

        self._bot = bot
        self._unsaved_state = False

        self._state_file = os.path.join(
            os.path.dirname(__file__), 'game_sessions.pickle')

        # dict of guilds with channels that have board games
        self._guilds: Guilds = self._load_state()

        self._task: asyncio.Task = self._bot.loop.create_task(
            self._save_state())

    def _load_state(self) -> Guilds:
        '''Load the state file to restore all game sessions'''
        if os.path.isfile(self._state_file):
            with open(self._state_file, 'rb') as in_file:
                guilds = pickle.load(in_file)
        else:
            guilds = {}
        return guilds

    async def _save_state(self):
        '''Task to be called on an interval, if state is changed then save new state'''
        while True:
            if self._unsaved_state:
                self._unsaved_state = False
                with open(self._state_file, 'wb') as out_file:
                    pickle.dump(self._guilds, out_file)
            await asyncio.sleep(SAVE_INTERVAL)

    @commands.group()
    async def chess(self, ctx: commands.Context):
        '''manage chess games'''

    @chess.group(name='start', autohelp=False)
    async def start_game(self, ctx: commands.Context,
                         other_player: discord.Member, game_name: str = None):
        '''sub command to start a new game'''

        # get games from self._guild
        channels = self._guilds[ctx.guild.id] = self._guilds.get(
            ctx.guild.id, {})
        games: Game
        games = channels[ctx.channel.id] = channels.get(ctx.channel.id, {})

        player_black = ctx.author
        player_white = other_player

        # init game_name if not provided
        if not game_name:
            game_name = f'{player_black.name} vs {player_white.name}'

        # make game_name unique if already exists
        count = 0
        suffix = ''
        while game_name + suffix in games.keys():
            count += 1
            suffix = f' - {count}'

        game_name += suffix

        game = Game(player_black.id, player_white.id)
        games[game_name] = game
        self._unsaved_state = True

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

        # owner can get a list of all servers and channels when whispering
        current_guild_channels = self._guilds.get(
            ctx.guild.id) if ctx.guild is not None else None
        guilds: Guilds
        is_owner = await ctx.bot.is_owner(ctx.author)
        if is_owner and ctx.guild is None:
            guilds = self._guilds
        else:
            if current_guild_channels:
                guilds = {ctx.guild.id: current_guild_channels}
            else:
                guilds = None

        if not guilds:
            embed.add_field(name=f"No Games Available",
                            value='You can start a new game with [p]chess start')
            await ctx.send(embed=embed)
            return

        for guild_id, channels in guilds.items():
            guild: discord.Guild = ctx.bot.get_guild(guild_id)
            embed.add_field(
                name=f'Server - {guild}', value='__List of channels:__', inline=False)
            for channel_id, games in channels.items():
                count = 0
                output = ''
                for game_name, game in games.items():
                    player_white = ctx.guild.get_member(game.player_white_id)
                    player_black = ctx.guild.get_member(game.player_black_id)

                    count += 1
                    output += f'\n** Game: #{count}** - __{game_name}__\n' \
                        f'```\tBlack: {player_black.name}\n' \
                        f'\tWhite: {player_white.name}\n' \
                        f'\tTotal Moves: {game.total_moves}```'

                embed.add_field(
                    name=f'Channel - {guild.get_channel(channel_id)}',
                    value='__List of games:__' + output)

        await ctx.send(embed=embed)

    @chess.group(name='move', autohelp=False)
    async def move_piece(self, ctx: commands.Context, game_name: str, move: str):
        '''move the next game piece, using Standard Algebraic Notation'''

        embed: discord.Embed = discord.Embed()

        try:
            game = self._guilds[ctx.guild.id][ctx.channel.id][game_name]
        except KeyError:
            # this game doesn't exist
            embed.title = f"Chess"
            embed.description = f"Game: {game_name}"
            embed.add_field(name=f"Game does not exist",
                            value=f"This game doesn't appear to exist, please check the "
                            "game list to ensure you are entering it correctly")
            await ctx.send(embed=embed)
            return

        player_white = ctx.guild.get_member(game.player_white_id)
        player_black = ctx.guild.get_member(game.player_black_id)

        if game.turn == chess.WHITE:
            turn_color = 'White'
            player_turn = player_white
            player_next = player_black
        else:
            turn_color = 'Black'
            player_turn = player_black
            player_next = player_white

        if player_turn == ctx.author:
            # it is their turn
            game.move_piece(move)
            self._unsaved_state = True

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
                            f"Only {player_black.name} (Black) and {player_white.name} ' \
                            '(White) are able to play in this game")
            await ctx.send(embed=embed)

    def __unload(self):
        if self._task:
            self._task.cancel()

    __del__ = __unload
