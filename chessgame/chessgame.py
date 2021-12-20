"""cog to play chess in discord"""
import io
import asyncio
from typing import Dict

import discord
import jsonpickle
from redbot.core import Config, commands
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

from .game import Game, start_help_text

# type hints
Games = Dict[str, Game]


class ChessGame(commands.Cog):
    """Cog to Play chess!"""

    _fifty_moves = 'Fifty moves'
    _threefold_repetition = 'Threefold repetition'

    def __init__(self):
        super().__init__()

        self._config = Config.get_conf(
            self, identifier=51314929031968350236701571200827144869558993811)

    async def _get_games(self, channel) -> Games:
        games_json = await self._config.channel(channel).games()
        if games_json:
            games = jsonpickle.decode(games_json)
            return games
        else:
            return None

    async def _set_games(self, channel, games):
        games_json = jsonpickle.encode(games)
        await self._config.channel(channel).games.set(games_json)

    @commands.group()
    async def chess(self, ctx: commands.Context):
        """manage chess games"""

    @chess.command(name='start', autohelp=False, help=start_help_text())
    async def start_game(self, ctx: commands.Context,
                         other_player: discord.Member,
                         game_name: str = None, game_type: str = None):
        """sub command to start a new game"""

        # let's ask the other player if they want to play the game!
        embed: discord.Embed = discord.Embed()

        embed.title = "Chess"
        embed.description = "New Game"

        embed.add_field(
            name=f"{ctx.author.name} would like to start a game!",
            value=f"<@{other_player.id}> respond below:")

        message = await ctx.send(embed=embed)

        # yes / no reaction options
        start_adding_reactions(message, ReactionPredicate.YES_OR_NO_EMOJIS)

        pred = ReactionPredicate.yes_or_no(
            message,
            other_player)

        create_game = True
        try:
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=600)
            if not pred.result:
                create_game = False
                embed.add_field(
                    name="Response:",
                    value="Game request was declined!")
        except asyncio.TimeoutError:
            create_game = False
            embed.add_field(
                name="Timed out:",
                value=f"<@{other_player.id}> did not respond in time.")

        if create_game:
            # remove message prompt
            await message.delete()
        else:
            # game will not be created
            # update message with response / timeout error
            await message.edit(embed=embed)
            await message.clear_reactions()
            return

        await self._start_game(ctx, ctx.author, other_player, game_name, game_type)

    @commands.is_owner()
    @chess.command(name='launch', autohelp=False, help=start_help_text())
    async def launch_game(self, ctx: commands.Context,
                          player: discord.Member, other_player: discord.Member,
                          game_name: str = None, game_type: str = None):
        """sub command to launch a new game between two members"""

        default_response = "Please Respond Below:"
        users = {player.id, other_player.id}

        responses = {
            player.id: {
                "name": player.name,
            },
            other_player.id: {
                "name": other_player.name,
            }
        }

        mention = ""
        for user in users:
            mention += f"<@{user}> "
        mention = mention.strip()

        def update_embed():
            # let's ask the other player if they want to play the game!
            embed: discord.Embed = discord.Embed()

            embed.title = "Chess"
            embed.description = (f"Start a new game between {player.name} and {other_player.name}."
                                 " Players, please respond below.")

            for response in responses.values():
                embed.add_field(
                    name=f"{response['name']}",
                    value=response.get("response", default_response))

            return embed

        embed = update_embed()
        message = await ctx.send(mention, embed=embed)

        # yes / no reaction options
        start_adding_reactions(message, ReactionPredicate.YES_OR_NO_EMOJIS)

        pred = ReactionPredicate.yes_or_no(message)
        try:
            while users:
                # wait for anyone to respond
                _reaction, user = await ctx.bot.wait_for("reaction_add", check=pred, timeout=600)

                if user.id in users:
                    if pred.result:
                        users.remove(user.id)

                        responses[user.id]["response"] = "Has accepted!"

                        embed = update_embed()
                        await message.edit(embed=embed)
                    else:
                        default_response = "The other player declined, no response required"
                        responses[user.id]["response"] = "Has declined!"

                        embed = update_embed()
                        await message.edit(embed=embed)

                        return
        except asyncio.TimeoutError:
            # one of, if not both users did not respond
            for user in users:
                responses[user]["response"] = "Did Not Respond! (Timed out)"

            embed = update_embed()
            await message.edit(embed=embed)

            return

        # game accepted! remove prompted message and start the game
        await message.delete()

        await self._start_game(ctx, player, other_player, game_name, game_type)

    async def _start_game(self, ctx: commands.Context,
                          player_black: discord.Member, player_white: discord.Member,
                          game_name: str = None, game_type: str = None):
        # get games config
        games = await self._get_games(ctx.channel)
        if not games:
            games = {}

        # init game_name if not provided
        if not game_name:
            game_name = f'game'

        # make game_name unique if already exists
        count = 0
        suffix = ''
        while game_name + suffix in games.keys():
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

        games[game_name] = game

        await self._set_games(ctx.channel, games)

        embed: discord.Embed = discord.Embed()
        embed.title = "Chess"
        embed.description = f"Game: {game_name}"
        embed.add_field(name="Type:", value=game.type, inline=False)

        embed.add_field(name="New Game",
                        value=f"<@{player_white.id}>'s (White's) turn is first",
                        inline=False)

        await self._display_board(ctx, embed, game)

    async def _display_board(self, ctx: commands.Context, embed: discord.Embed, game: Game):
        """displays the game board"""
        board_image = io.BytesIO(game.get_board_image())
        embed.set_image(url="attachment://board.png")
        await ctx.send(embed=embed, file=discord.File(board_image, 'board.png'))

    @chess.command(name='list', autohelp=False)
    async def list_games(self, ctx: commands.Context):
        """list all available games"""
        no_games = True

        max_len = 1000

        embed: discord.Embed = discord.Embed()

        embed.title = "Chess"
        embed.description = "Chess Game List"

        total_len = len(embed.title) + len(embed.description)

        for channel in ctx.guild.channels:
            games = await self._get_games(channel)
            count = 0
            output = ''

            if not games:
                continue
            no_games = False

            for game_name, game in games.items():
                player_white = ctx.guild.get_member(game.player_white_id)
                player_black = ctx.guild.get_member(game.player_black_id)

                count += 1
                current_game = f'\n** Game: #{count}** - __{game_name}__\n' \
                    f'```Black: {player_black.name}\n' \
                    f'White: {player_white.name}\n' \
                    f'Total Moves: {game.total_moves}\n' \
                    f'Type: {game.type}```'

                current_game_len = len(current_game)

                # send it now if we hit our limit
                if total_len + current_game_len > max_len:
                    embed.add_field(
                        name=f'Channel - {channel}',
                        value='__List of games:__' + output,
                        inline=False)
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
                name=f'Channel - {channel}',
                value='__List of games:__' + output,
                inline=False)

        if no_games:
            embed.add_field(name="No Games Available",
                            value='You can start a new game with [p]chess start')
            await ctx.send(embed=embed)
        elif total_len > 0:
            await ctx.send(embed=embed)

    @chess.command(name='move', autohelp=False)
    async def move_piece(self, ctx: commands.Context, game_name: str, move: str):
        """move the next game piece, using Standard Algebraic Notation"""

        embed: discord.Embed = discord.Embed()
        embed.title = "Chess"
        embed.description = f"Game: {game_name}"

        try:
            games = await self._get_games(ctx.channel)
            game = games[game_name]
        except KeyError:
            # this game doesn't exist
            embed.add_field(name="Game does not exist",
                            value="This game doesn't appear to exist, please check the "
                            "game list to ensure you are entering it correctly")
            await ctx.send(embed=embed)
            return

        embed.add_field(name="Type:", value=game.type, inline=False)

        player_white = ctx.guild.get_member(game.player_white_id)
        player_black = ctx.guild.get_member(game.player_black_id)

        turn_color, player_turn, player_next = game.order
        # convert ids to members
        if player_turn == game.player_white_id:
            player_turn = player_white
            player_next = player_black
        else:
            player_turn = player_black
            player_next = player_white

        if player_turn == ctx.author:
            # it is their turn
            try:
                is_game_over, value_move = game.move_piece(move)
            except ValueError:
                embed.add_field(name="Invalid Move Taken!",
                                value=f"'{move}' isn't a valid move, try again.")
                await ctx.send(embed=embed)
                return

            name_move = f"Move: {game.total_moves} - " \
                f"{player_turn.name}'s ({turn_color}'s) Turn"

            if is_game_over:
                del games[game_name]
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

            await self._set_games(ctx.channel, games)

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
        """draw related commands"""

    @draw.command(name='claim', autohelp=False)
    async def claim_draw(self, ctx: commands.Context, game_name: str, claim_type: str):
        """if valid claim made to draw the game will end with no victor"""

        embed: discord.Embed = discord.Embed()

        embed.title = "Chess"
        embed.description = "Claim Draw"

        try:
            games = await self._get_games(ctx.channel)
            game = games[game_name]
        except KeyError:
            embed.add_field(name="Game does not exist",
                            value="This game doesn't appear to exist, please check the "
                            "game list to ensure you are entering it correctly")
            await ctx.send(embed=embed)
            return

        if self._fifty_moves == claim_type and game.can_claim_fifty_moves:
            embed.add_field(
                name=f'Draw! - {claim_type}',
                value='There are been no captures or pawns moved in the last 50 moves'
            )
            del games[game_name]
            await self._set_games(ctx.channel, games)
        elif self._threefold_repetition == claim_type and game.can_claim_threefold_repetition:
            embed.add_field(
                name=f'Draw! - {claim_type}',
                value='Position has occured five times'
            )
            del games[game_name]
            await self._set_games(ctx.channel, games)
        else:
            embed.add_field(
                name=claim_type,
                value=f'Unable to claim {claim_type}\n'
                f'{claim_type} is not a valid reason, the game is not drawn.'
            )

        await ctx.send(embed=embed)

    @draw.group(name='byagreement', autohelp=False)
    async def by_agreement(self, ctx: commands.Context, game_name: str):
        """Offer draw by agreement"""

        embed: discord.Embed = discord.Embed()

        embed.title = "Chess"
        embed.description = "Offer Draw"

        try:
            games = await self._get_games(ctx.channel)
            game = games[game_name]
        except KeyError:
            embed.add_field(name="Game does not exist",
                            value="This game doesn't appear to exist, please check the "
                            "game list to ensure you are entering it correctly")
            await ctx.send(embed=embed)
            return

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

        embed.add_field(
            name=f"{ctx.author.name} has offered a draw",
            value=f"<@{other_player}> respond below:")

        message = await ctx.send(embed=embed)

        # yes / no reaction options
        start_adding_reactions(message, ReactionPredicate.YES_OR_NO_EMOJIS)

        pred = ReactionPredicate.yes_or_no(
            message,
            ctx.guild.get_member(other_player))
        try:
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=30)
            if pred.result is True:
                embed.add_field(
                    name="Response:",
                    value="Draw accepted!")
                del games[game_name]
                await self._set_games(ctx.channel, games)
            else:
                embed.add_field(
                    name="Response:",
                    value="Draw declined!")
        except asyncio.TimeoutError:
            embed.add_field(
                name="Timed out:",
                value=f"<@{other_player}> did not respond in time.")

        await message.edit(embed=embed)
        await message.clear_reactions()

    @commands.is_owner()
    @chess.command()
    async def close(self,
                    ctx: commands.Context,
                    game_name: str,
                    channel: discord.TextChannel = None):
        """sub command to close a game"""

        embed: discord.Embed = discord.Embed()

        embed.title = "Chess"
        embed.description = "Close Game"

        if channel is None:
            channel = ctx.channel

        try:
            games = await self._get_games(channel)
        except KeyError:
            embed.add_field(name="Game does not exist",
                            value="This game doesn't appear to exist, please check the "
                            "game list to ensure you are entering it correctly.")
            await ctx.send(embed=embed)
            return

        embed.add_field(
            name=f"Do you really want to delete this game?",
            value=f"<@{ctx.author.id}> respond below:")

        message = await ctx.send(embed=embed)

        # yes / no reaction options
        start_adding_reactions(message, ReactionPredicate.YES_OR_NO_EMOJIS)

        pred = ReactionPredicate.yes_or_no(
            message,
            ctx.guild.get_member(ctx.author.id))
        try:
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=10)
            if pred.result is True:
                embed.add_field(
                    name="Response:",
                    value="Game closed!")
                del games[game_name]
                await self._set_games(ctx.channel, games)
                await message.edit(embed=embed)
                await message.clear_reactions()
            else:
                embed.add_field(
                    name="Response:",
                    value="Close declined!")
                await message.edit(embed=embed)
                await message.clear_reactions()
        except asyncio.TimeoutError:
            await message.clear_reactions()
            await message.delete(embed=embed)
