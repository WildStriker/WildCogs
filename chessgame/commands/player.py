
"""module contains logic for game related commands"""
import asyncio
import math

import discord
from redbot.core import commands
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

from ..constants import DEFAULT_ELO
from ..game import start_help_text
from .main import chess


class PlayerCommands:
    """Game related commands"""

    _fifty_moves = 'Fifty moves'
    _threefold_repetition = 'Threefold repetition'

    @chess.command(name="start", autohelp=False, help=start_help_text())
    async def start_game(self, ctx: commands.Context,
                         other_player: discord.Member,
                         game_name: str = None, game_type: str = None):
        """sub command to start a new game"""

        # let's ask the other player if they want to play the game!
        embed: discord.Embed = discord.Embed()

        embed.title = "Chess"
        embed.description = "New Game"

        if other_player.bot:
            bot = other_player
            embed.add_field(
                name=f"{bot} is a bot!",
                value="You cannot start a game with a bot.")
            message = await ctx.send(embed=embed)
            return

        embed.add_field(
            name=f"{ctx.author.name} would like to start a game!",
            value=f"<@{other_player.id}> respond below:")

        message = await ctx.send(f"<@{other_player.id}>", embed=embed)

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

    @chess.command(name="move", autohelp=False)
    async def move_piece(self, ctx: commands.Context, game_name: str, move: str):
        """move the next game piece, using Standard Algebraic Notation"""

        embed: discord.Embed = discord.Embed()
        embed.title = "Chess"
        embed.description = f"Game: {game_name}"

        try:
            game = await self._get_game(ctx.channel, game_name)
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

        turn_color, player_turn, player_next = game.get_order(False)
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
                move_result = game.move_piece(move)
            except ValueError:
                embed.add_field(name="Invalid Move Taken!",
                                value=f"'{move}' isn't a valid move, try again.")
                await ctx.send(embed=embed)
                return

            name_move = f"Move: {game.total_moves} - " \
                f"{player_turn.name}'s ({turn_color}'s) Turn"

            if move_result.is_game_over:
                if move_result.winner_id:
                    await self._finish_game(ctx,
                                            game_name,
                                            False,
                                            move_result.winner_id,
                                            move_result.loser_id)
                else:
                    await self._finish_game(ctx,
                                            game_name,
                                            True,
                                            player_turn,
                                            player_next)

                embed.add_field(
                    name="Game Over!",
                    value="Match is over! Start a new game if you want to play again.")
            else:
                await self._set_game(ctx.channel, game_name, game)

            embed.add_field(name=name_move,
                            value=move_result.message)

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

            await self._display_board(ctx, move_result.mention, embed, game)
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

    @chess.group(name="draw")
    async def draw(self, ctx: commands.Context):
        """draw related commands"""

    @draw.command(name='claim', autohelp=False)
    async def claim_draw(self, ctx: commands.Context, game_name: str, claim_type: str):
        """if valid claim made to draw the game will end with no victor"""

        embed: discord.Embed = discord.Embed()

        embed.title = "Chess"
        embed.description = "Claim Draw"

        try:
            game = await self._get_game(ctx.channel, game_name)
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
            await self._finish_game(ctx,
                                    game_name,
                                    True,
                                    game.player_black_id,
                                    game.player_white_id)
        elif self._threefold_repetition == claim_type and game.can_claim_threefold_repetition:
            embed.add_field(
                name=f'Draw! - {claim_type}',
                value='Position has occured five times'
            )
            await self._finish_game(ctx,
                                    game_name,
                                    True,
                                    game.player_black_id,
                                    game.player_white_id)
        else:
            embed.add_field(
                name=claim_type,
                value=f'Unable to claim {claim_type}\n'
                f'{claim_type} is not a valid reason, the game is not drawn.'
            )

        await ctx.send(embed=embed)

    @draw.group(name="byagreement", autohelp=False)
    async def by_agreement(self, ctx: commands.Context, game_name: str):
        """Offer draw by agreement"""

        embed: discord.Embed = discord.Embed()

        embed.title = "Chess"
        embed.description = "Offer Draw"

        try:
            game = await self._get_game(ctx.channel, game_name)
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

        message = await ctx.send(f"<@{other_player}>", embed=embed)

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
                await self._finish_game(ctx,
                                        game_name,
                                        True,
                                        game.player_black_id,
                                        game.player_white_id)
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

    async def _finish_game(self,
                           ctx: commands.Context,
                           game_name: str,
                           is_draw: bool,
                           player_1: int,
                           player_2: int):
        """helper function to close game and update scoreboard when finished

        first player id should be the winner if the game did not end in a draw

        Args:
            ctx (commands.Context): command context
            game_name (str): game name that will be removed from config
            is_draw (bool): True if game ended in a draw
            player_1 (int): first player id, this is the winner if not a draw
            player_2 (int): second player id, this is the winner if not a draw
        """
        await self.config.channel(ctx.channel).games.clear_raw(game_name)

        # do not update the scoreboard if someone
        # is just playing against themselves
        if player_1 == player_2:
            return

        if is_draw:
            elo_offset_1, elo_offset_2 = await self._calculate_elo_offset(
                ctx.guild,
                player_1,
                player_2,
                0.5)
            await self._increment_score(ctx.guild, player_1, elo_offset_1, 0, 0, 1)
            await self._increment_score(ctx.guild, player_2, elo_offset_2, 0, 0, 1)
        else:
            elo_offset_1, elo_offset_2 = await self._calculate_elo_offset(
                ctx.guild,
                player_1,
                player_2,
                1)
            await self._increment_score(ctx.guild, player_1, elo_offset_1, 1, 0, 0)
            await self._increment_score(ctx.guild, player_2, elo_offset_2, 0, 1, 0)

    async def _calculate_elo_offset(self, guild, player_1, player_2, player_1_score):
        player_1_elo = await self.config.guild(guild).scoreboard.get_raw(
            str(player_1),
            "elo",
            default=DEFAULT_ELO)
        player_2_elo = await self.config.guild(guild).scoreboard.get_raw(
            str(player_2),
            "elo",
            default=DEFAULT_ELO)

        expected_score_1 = 1 / (1 + math.pow(10,
                                             (player_2_elo - player_1_elo) / 400))
        expected_score_2 = 1 - expected_score_1

        k_factor = 32

        player_2_score = 1 - player_1_score

        calculate_1 = k_factor * (player_1_score - expected_score_1)
        calculate_2 = k_factor * (player_2_score - expected_score_2)

        return round(calculate_1), round(calculate_2)
