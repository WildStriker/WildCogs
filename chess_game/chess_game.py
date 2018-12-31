'''cog to play chess in discord'''
import asyncio
import os
import pickle
from typing import Dict

import cairosvg
import chess
import chess.svg
import discord
from redbot.core import commands
from redbot.core.bot import Red

SAVE_INTERVAL = 30


class Game:
    '''class used to hold state of a game'''

    _style = 'text {' \
        'fill: orange' \
        '}'

    def __init__(self, player_black_id, player_white_id):

        self._board = chess.Board()
        self._arrows = ()

        self._player_black_id = player_black_id
        self._player_white_id = player_white_id
        self._draw_offer_by = None

    def get_board_text(self) -> str:
        '''returns the game board as text'''
        return str(self._board)

    def get_board_image(self) -> bytes:
        '''returns the game as an image

        can't embed svg, so convert to png first
        '''

        lastmove = self._board.peek() if self._board.move_stack else None
        check = self._board.king(self.turn) if self._board.is_check() else None

        # get svg string
        svg_board = chess.svg.board(
            board=self._board,
            lastmove=lastmove,
            check=check,
            arrows=self._arrows,
            style=self._style).encode()

        # convert to png
        image_board = cairosvg.svg2png(bytestring=svg_board)
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
    def player_white_id(self) -> str:
        '''returns the player assigned to white pieces'''
        return self._player_white_id

    @property
    def player_black_id(self) -> str:
        '''returns the player assigned to black pieces'''
        return self._player_black_id

    @property
    def draw_offer_by(self) -> str:
        '''returns the id of the player who offered draw'''
        return self._draw_offer_by

    @draw_offer_by.setter
    def draw_offer_by(self, player_id: str):
        '''sets the id of the player who offered draw'''
        self._draw_offer_by = player_id

    @property
    def is_check(self) -> bool:
        '''true if in check'''
        return self._board.is_check()

    @property
    def is_checkmate(self) -> bool:
        '''true if in checkmate'''
        return self._board.is_checkmate()

    @property
    def is_stalemate(self) -> bool:
        '''true if draw by statemate'''
        return self._board.is_stalemate()

    @property
    def is_insufficient_material(self) -> bool:
        '''true if draw by insufficient material'''
        return self._board.is_insufficient_material()

    @property
    def is_seventyfive_moves(self) -> bool:
        '''true if draw by seventyfive moves'''
        return self._board.is_seventyfive_moves()

    @property
    def is_fivefold_repetition(self) -> bool:
        '''true if draw by fivefold repetition'''
        return self._board.is_fivefold_repetition()

    @property
    def can_claim_draw(self):
        '''true if players can claim a draw'''
        return self._board.can_claim_draw()

    @property
    def can_claim_fifty_moves(self):
        '''true if players can claim a draw by fifty moves'''
        return self._board.can_claim_fifty_moves()

    @property
    def can_claim_threefold_repetition(self):
        '''true if players can claim a draw by threefold repetition'''
        return self._board.can_claim_threefold_repetition()


# type hints
Games = Dict[str, Game]
Channels = Dict[str, Games]
Guilds = Dict[str, Channels]


class Chess(commands.Cog):
    '''Cog to Play chess!'''

    _fifty_moves = 'Fifty moves'
    _threefold_repetition = 'Threefold repetition'

    def __init__(self, bot: Red):
        super().__init__()

        self._bot = bot
        self._unsaved_state = False

        self._state_file = os.path.join(
            os.path.dirname(__file__), 'game_sessions.pickle')

        # dict of guilds with channels that have board games
        self._guilds: Guilds = self._load_state()

        self._task: asyncio.Task = self._bot.loop.create_task(
            self._save_state_loop())

    def _load_state(self) -> Guilds:
        '''Load the state file to restore all game sessions'''
        if os.path.isfile(self._state_file):
            with open(self._state_file, 'rb') as in_file:
                guilds = pickle.load(in_file)
        else:
            guilds = {}
        return guilds

    async def _save_state_loop(self):
        '''Task to be called on an interval, if state is changed then save new state'''
        while True:
            self._save_state()
            await asyncio.sleep(SAVE_INTERVAL)

    def _save_state(self):
        '''save state of all on going games'''
        if self._unsaved_state:
            self._unsaved_state = False
            with open(self._state_file, 'wb') as out_file:
                pickle.dump(self._guilds, out_file)

    @commands.group()
    async def chess(self, ctx: commands.Context):
        '''manage chess games'''

    @chess.command(name='start', autohelp=False)
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

    @chess.command(name='list', autohelp=False)
    async def list_games(self, ctx: commands.Context):
        '''list all available games'''

        max_len = 1000

        embed: discord.Embed = discord.Embed()

        embed.title = "Chess"
        embed.description = "Chess Game List"

        total_len = len(embed.title) + len(embed.description)

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
            embed.add_field(name="No Games Available",
                            value='You can start a new game with [p]chess start')
            await ctx.send(embed=embed)
            return

        for guild_id, channels in guilds.items():
            guild: discord.Guild = ctx.bot.get_guild(guild_id)
            server_name = f'Server - {guild}'
            server_value = '__List of channels:__'
            total_len += len(server_name) + len(server_value)
            embed.add_field(
                name=server_name,
                value=server_value,
                inline=False)
            for channel_id, games in channels.items():
                count = 0
                output = ''
                for game_name, game in games.items():
                    player_white = guild.get_member(game.player_white_id)
                    player_black = guild.get_member(game.player_black_id)

                    count += 1
                    current_game = f'\n** Game: #{count}** - __{game_name}__\n' \
                        f'```\tBlack: {player_black.name}\n' \
                        f'\tWhite: {player_white.name}\n' \
                        f'\tTotal Moves: {game.total_moves}```'

                    current_game_len = len(current_game)

                    # send it now if we hit our limit
                    if total_len + current_game_len > max_len:
                        embed.add_field(
                            name=f'Channel - {guild.get_channel(channel_id)}',
                            value='__List of games:__' + output)
                        output = current_game
                        total_len = current_game_len

                        await ctx.send(embed=embed)
                        embed: discord.Embed = discord.Embed()

                        embed.title = "Chess"
                        embed.description = "Chess Game List - Continued"
                    else:
                        output += current_game
                        total_len += current_game_len

                # add field for remaining
                embed.add_field(
                    name=f'Channel - {guild.get_channel(channel_id)}',
                    value='__List of games:__' + output)

        if total_len > 0:
            await ctx.send(embed=embed)

    @chess.command(name='move', autohelp=False)
    async def move_piece(self, ctx: commands.Context, game_name: str, move: str):
        '''move the next game piece, using Standard Algebraic Notation'''

        embed: discord.Embed = discord.Embed()
        embed.title = "Chess"
        embed.description = f"Game: {game_name}"

        try:
            game = self._guilds[ctx.guild.id][ctx.channel.id][game_name]
        except KeyError:
            # this game doesn't exist
            embed.add_field(name="Game does not exist",
                            value="This game doesn't appear to exist, please check the "
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
            try:
                game.move_piece(move)
            except ValueError:
                embed.add_field(name="Invalid Move Taken!",
                                value=f"'{move}' isn't a valid move, try again.")
                await ctx.send(embed=embed)
                return

            name_move = f"Move: {game.total_moves} - " \
                f"{player_turn.name}'s ({turn_color}'s) Turn"

            is_game_over = False
            if game.is_checkmate:
                is_game_over = True
                value_move = f"Checkmate! <@{ctx.author.id}> Wins!"
            elif game.is_check:
                value_move = f"<@{player_next.id}> you are in check. Your move is next."
            elif game.is_stalemate:
                is_game_over = True
                value_move = "Draw by stalemate!\n" \
                    f"<@{player_next.id}> is not in check and can only move into check! !"
            elif game.is_insufficient_material:
                is_game_over = True
                value_move = "Draw by insufficient material!\n" \
                    "Neither player has enough pieces to win"
            elif game.is_seventyfive_moves:
                is_game_over = True
                value_move = "Draw by seventyfive moves rule!" \
                    "There are been no captures or pawns moved in the last 75 moves"
            elif game.is_fivefold_repetition:
                is_game_over = True
                value_move = "Draw by fivefold repetition!" \
                    "Position has occured five times"
            else:
                value_move = f"<@{player_next.id}> you're up next!"

            if is_game_over:
                self._remove_game(ctx.guild.id, ctx.channel.id, game_name)
                embed.add_field(
                    name="Game Over!",
                    value="Match is over! Start a new game if you want to play again.")

            embed.add_field(name=name_move,
                            value=value_move)

            # show if can claim draw
            if game.can_claim_draw:

                if game.can_claim_fifty_moves:
                    fifty_moves = f'\n"{self._fifty_moves }"'
                else:
                    fifty_moves = ''

                if game.can_claim_threefold_repetition:
                    threefold_repetition = f'\n"{self._threefold_repetition}"'
                else:
                    threefold_repetition = ''

                embed.add_field(
                    name='Draw can be claimed',
                    value='To end this game now use "[p]chess draw claim" with:' +
                    fifty_moves +
                    threefold_repetition)

            self._unsaved_state = True

            await self._display_board(ctx, embed, game)
        elif player_next == ctx.author:
            # not their turn yet
            embed.add_field(name=f"{player_next.name} - not your turn",
                            value=f"{player_next.name} it doesn't look like its your turn yet! "
                            f"<@{player_turn.id}> ({turn_color}) still needs to make a move "
                            "before you can.")
            await ctx.send(embed=embed)
        else:
            # not a player
            embed.add_field(name=f"{ctx.author.name} - not a player",
                            value=f"{ctx.author.name} you are not part of this game!\n"
                            f"Only {player_black.name} (Black) and {player_white.name} ' \
                            '(White) are able to play in this game")
            await ctx.send(embed=embed)

    @chess.group(name='draw')
    async def draw(self, ctx: commands.Context):
        '''draw related commands'''

    @draw.command(name='claim', autohelp=False)
    async def claim_draw(self, ctx: commands.Context, game_name: str, claim_type: str):
        '''if valid claim made to draw the game will end with no victor'''

        game = self._guilds[ctx.guild.id][ctx.channel.id][game_name]

        embed: discord.Embed = discord.Embed()

        embed.title = "Chess"
        embed.description = "Claim Draw"

        if self._fifty_moves == claim_type and game.can_claim_fifty_moves:
            embed.add_field(
                name=f'Draw! - {claim_type}',
                value='There are been no captures or pawns moved in the last 50 moves'
            )
            self._remove_game(ctx.guild.id, ctx.channel.id, game_name)
        elif self._threefold_repetition == claim_type and game.can_claim_threefold_repetition:
            embed.add_field(
                name=f'Draw! - {claim_type}',
                value='Position has occured five times'
            )
            self._remove_game(ctx.guild.id, ctx.channel.id, game_name)
        else:
            embed.add_field(
                name=claim_type,
                value=f'Unable to claim {claim_type}\n'
                f'{claim_type} is not a valid reason, the game is not drawn.'
            )

        await ctx.send(embed=embed)

    @draw.group(name='byagreement')
    async def by_agreement(self, ctx: commands.Context):
        '''end game by draw if both players agree'''

    @by_agreement.command(name='offer', autohelp=False)
    async def offer_draw(self, ctx: commands.Context, game_name: str):
        '''Offer draw by agreement'''

        game = self._guilds[ctx.guild.id][ctx.channel.id][game_name]

        embed: discord.Embed = discord.Embed()

        embed.title = "Chess"
        embed.description = "Offer Draw"

        # identify the other player to mention
        if ctx.author.id == game.player_black_id:
            other_player = game.player_white_id
        elif ctx.author.id == game.player_white_id:
            other_player = game.player_black_id
        else:  # not part of this game
            embed.add_field(
                name="You are not part of this game",
                value="You are not able to offer a draw if you are not one of the players.")
            await ctx.send(embed=embed)
            return

        if game.draw_offer_by:
            if game.draw_offer_by == ctx.author.id:
                embed.add_field(
                    name="Offer Already Given",
                    value="You have already offered a draw, wait for the other players response")
            else:
                embed.add_field(
                    name="You Must Accept Offer",
                    value="The other player has offered a draw, "
                    "please respond with the accept subcommand instead.")
        else:
            game.draw_offer_by = ctx.author.id
            embed.add_field(
                name=f"{ctx.author.name} has offered a draw",
                value=f"<@{other_player}> please response back with "
                "the accept or decline subcommand")
        await ctx.send(embed=embed)

    @by_agreement.command(name='accept', autohelp=False)
    async def accept_draw(self, ctx: commands.Context, game_name: str):
        '''Accept draw by agreement if the other player offered'''
        game = self._guilds[ctx.guild.id][ctx.channel.id][game_name]

        embed: discord.Embed = discord.Embed()

        embed.title = "Chess"
        embed.description = "Accept Draw"

        # identify the player that offered draw
        if ctx.author.id == game.player_black_id:
            other_player = game.player_white_id
        elif ctx.author.id == game.player_white_id:
            other_player = game.player_black_id
        else:  # not part of this game
            embed.add_field(
                name="You are not part of this game",
                value="You are not able to accept a draw if you are not one of the players.")
            await ctx.send(embed=embed)
            return

        if game.draw_offer_by:
            if other_player == game.draw_offer_by:
                embed.add_field(
                    name=f'{ctx.author.name} Accepts',
                    value='Game has ended in a draw by agreement!')

                self._remove_game(ctx.guild.id, ctx.channel.id, game_name)
            else:
                embed.add_field(
                    name='Cannot Accept',
                    value=f'You can not accept if you are the one that has offered the draw'
                )
        else:
            embed.add_field(
                name='No Draw Offer',
                value='No one has offered draw by agreement'
            )

        await ctx.send(embed=embed)

    @by_agreement.command(name='decline', autohelp=False)
    async def decline_draw(self, ctx: commands.Context, game_name: str):
        '''Decline draw by agreement.  Can be done by either player'''
        game = self._guilds[ctx.guild.id][ctx.channel.id][game_name]

        embed: discord.Embed = discord.Embed()

        embed.title = "Chess"
        embed.description = "Decline Draw"

        # can't decline if they aren't in the game
        if ctx.author.id != game.player_black_id and ctx.author.id == game.player_white_id:
            embed.add_field(
                name="You are not part of this game",
                value="You are not able to decline a draw if you are not one of the players.")
            await ctx.send(embed=embed)
            return

        if game.draw_offer_by:
            embed.add_field(
                name=f'{ctx.author.name} Declined',
                value='Draw by agreement has been decline, the game continues!')

            self._unsaved_state = True
            game.draw_offer_by = None
        else:
            embed.add_field(
                name='No Draw Offer',
                value='No one has offered draw by agreement'
            )

        await ctx.send(embed=embed)

    def _remove_game(self, guild_id: str, channel_id: str, game_name: str):
        '''clean up, remove the game and channel / guild if no games / channels remains'''
        self._unsaved_state = True

        del self._guilds[guild_id][channel_id][game_name]

        if not self._guilds[guild_id][channel_id]:
            del self._guilds[guild_id][channel_id]
        else:
            return

        if not self._guilds[guild_id]:
            del self._guilds[guild_id]

    def __unload(self):
        if self._task:
            self._task.cancel()

        # call once more before unloading
        self._save_state()

    __del__ = __unload
