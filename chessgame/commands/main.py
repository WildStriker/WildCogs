"""Main command module
"""
import asyncio
import typing

import discord
from redbot.core import commands
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

from ..game import start_help_text


class MainCommands:
    """Main Command

    contains root command, as well as any other not grouped by function"""
    @commands.group()
    async def chess(self, ctx: commands.Context):
        """manage chess games"""

    @chess.command(name='show', autohelp=False)
    async def show_game(self, ctx: commands.Context, game_name: str):
        """reposts the last gameboard state"""
        embed: discord.Embed = discord.Embed()
        embed.title = "Chess"
        embed.description = f"Game: {game_name}"

        try:
            game = await self._get_game(ctx.channel, game_name)
        except ValueError:
            embed.add_field(name="Game does not exist",
                            value="This game doesn't appear to exist, please check the "
                            "game list to ensure you are entering it correctly")
            await ctx.send(embed=embed)
            return

        embed.add_field(name="Type:", value=game.type, inline=False)

        turn_color, player_turn, _player_next = game.get_order(True)
        mention = f"<@{player_turn}>"

        player_turn = ctx.guild.get_member(player_turn)

        if game.total_moves == 0:
            name_move = "New Game"
            value = f"<@{player_turn.id}>'s (White's) turn is first"
        else:
            name_move = f"Move: {game.total_moves} - " \
                f"{player_turn.name}'s ({turn_color}'s) Turn"
            value = f"{mention} you're up next!"

        embed.add_field(name=name_move,
                        value=value,
                        inline=False)

        await self._display_board(ctx, mention, embed, game)

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

    @commands.is_owner()
    @chess.command()
    async def close(self,
                    ctx: commands.Context,
                    game_name: str,
                    channel: typing.Optional[discord.TextChannel] = None,
                    no_confirmation: typing.Optional[bool] = False):
        """sub command to close a game"""

        embed: discord.Embed = discord.Embed()

        embed.title = "Chess"
        embed.description = "Close Game"

        if channel is None:
            channel = ctx.channel

        if game_name not in await self.config.channel(ctx.channel).games():
            embed.add_field(name="Game does not exist",
                            value="This game doesn't appear to exist, please check the "
                            "game list to ensure you are entering it correctly.")
            await ctx.send(embed=embed)
            return

        if not no_confirmation:
            embed.add_field(
                name="Do you really want to delete this game?",
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
                    await self.config.channel(ctx.channel).games.clear_raw(game_name)
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
                await message.delete()
        else:
            await self.config.channel(ctx.channel).games.clear_raw(game_name)
            embed.add_field(
                name="Response:",
                value="Game closed!")
            await ctx.send(embed=embed)


# for conveniently making group available to other command classes
chess = MainCommands.chess
