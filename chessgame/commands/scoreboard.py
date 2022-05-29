
"""module contains logic for scoreboard related commands"""
import asyncio
import math
from typing import Union

import discord
from redbot.core import commands
from redbot.core.utils.menus import (DEFAULT_CONTROLS, menu,
                                     start_adding_reactions)
from redbot.core.utils.predicates import ReactionPredicate

from .main import chess


class ScoreboardCommands:
    """Scoreboard related commands"""

    @chess.group(name="scoreboard")
    async def scoreboard(self, ctx: commands.Context):
        """scoreboard related commands"""

    @scoreboard.command(name="list", autohelp=False)
    async def list_all(self, ctx: commands.Context, sort_by: str = "wins"):
        """list users scoreboard from highest to lowest

        Scoreboard can be sorted by elo, wins, losses, or ties.
        Scoreboard is sorted by wins by default."""
        players_per_page = 10
        max_characters = 26
        output_start = "```Rank Player    (elo) W-L-T"

        scoreboard = await self.config.guild(ctx.guild).scoreboard()
        total_players = len(scoreboard)

        if sort_by not in {"elo", "wins", "losses", "ties"}:
            embed: discord.Embed = discord.Embed()

            embed.title = "Chess"
            embed.description = "Scoreboard"

            embed.add_field(
                name="Invalid key for sorting",
                value="Please enter a valid sort option (elo, wins, losses, ties)"
            )
            await ctx.send(embed=embed)
            return

        if not total_players:
            embed: discord.Embed = discord.Embed()

            embed.title = "Chess"
            embed.description = "Scoreboard"

            embed.add_field(
                name="No players to list",
                value="The scoreboard is currently empty."
            )
            await ctx.send(embed=embed)
            return

        total_pages = math.ceil(total_players / players_per_page)

        scoreboard = sorted(scoreboard.items(),
                            key=lambda item: item[1][sort_by],
                            reverse=True)

        pages = []
        output = output_start
        count = 0
        for index, (user_id, score) in enumerate(scoreboard, 1):
            user = ctx.guild.get_member(int(user_id))

            if user:
                user_name = user.name
            else:
                user_name = f"Unknown User (ID: {user_id})"

            current_line = f"{index:<5}{user_name}"
            left_len = len(current_line)

            output += f"\n{current_line}"
            formatted_score = f" ({score['elo']}) {score['wins']}-{score['losses']}-{score['ties']}"
            if left_len + len(formatted_score) > max_characters:
                output += f"\n{formatted_score:>{max_characters}}"
            else:
                output += f" {formatted_score:>{max_characters - left_len - 1}}"

            count += 1
            offset = count % players_per_page
            if offset == 0 or count == total_players:
                if offset == 0:
                    offset = 10

                output += "```"

                embed: discord.Embed = discord.Embed()

                embed.title = "Chess"
                embed.description = "Scoreboard"

                embed.add_field(
                    name=f"Players #{index-offset+1}-{index}",
                    value=output
                )

                embed.set_footer(
                    text=f"Page {len(pages) + 1} of {total_pages}")

                pages.append(embed)
                output = output_start

        await menu(ctx, pages, DEFAULT_CONTROLS)

    @scoreboard.command(name="find", autohelp=False)
    async def find(self, ctx: commands.Context, player: discord.Member = None):
        """find a player's score. If none is provided this will look for the requester's score"""

        try:
            score = await self.config.guild(ctx.guild).scoreboard.get_raw(str(player.id))
            info = (f"__{player.name}__\n```"
                    f"ELO: {score['elo']}\n"
                    f"WINS: {score['wins']}\n"
                    f"LOSSES: {score['losses']}\n"
                    f"TIES: {score['ties']}```")
        except KeyError:
            info = f"No score data exists for {player.name}"

        embed: discord.Embed = discord.Embed()

        embed.title = "Chess"
        embed.description = "Player's Score"

        embed.add_field(
            name="Player:",
            value=info
        )
        await ctx.send(embed=embed)

    @commands.is_owner()
    @scoreboard.command(name="increment", autohelp=False)
    async def increment(self,
                        ctx: commands.Context,
                        player: discord.Member,
                        elo: int,
                        wins: int,
                        losses: int,
                        ties: int):
        """allows bot owner to increment (decrement if negative value passed) a player's score"""
        try:
            old_score = await self.config.guild(ctx.guild).scoreboard.get_raw(str(player.id))
        except KeyError:
            old_score = {}
        await self._increment_score(ctx.guild, player.id, elo, wins, losses, ties)
        new_score = await self.config.guild(ctx.guild).scoreboard.get_raw(str(player.id))

        info = (f"__{player.name}__\n```"
                f"ELO: {old_score.get('elo', 'N/A')} -> {new_score['elo']}\n"
                f"WINS: {old_score.get('wins', 'N/A')} -> {new_score['wins']}\n"
                f"LOSSES: {old_score.get('losses', 'N/A')} -> {new_score['losses']}\n"
                f"TIES Moves: {old_score.get('ties', 'N/A')} -> {new_score['ties']}```")

        embed: discord.Embed = discord.Embed()

        embed.title = "Chess"
        embed.description = "Increment Score"

        embed.add_field(
            name="Updated Player's Score:",
            value=info
        )
        await ctx.send(embed=embed)

    @commands.is_owner()
    @scoreboard.group(name="clear")
    async def clear(self, ctx: commands.Context):
        """allows bot owner clear the scoreboard"""

    @commands.is_owner()
    @clear.command(name="all", autohelp=False)
    async def clear_all(self, ctx: commands.Context):
        """remove **ALL** scores from the scoreboard"""

        embed: discord.Embed = discord.Embed()

        embed.title = "Chess"
        embed.description = "Clear Scoreboard"

        embed.add_field(
            name="Do you really want to clear the __entire__ scoreboard?",
            value=f"This cannot be undone, <@{ctx.author.id}> respond below:")

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
                    value="Scoreboard has been completely cleared.")
                await self.config.guild(ctx.guild).scoreboard.clear()
            else:
                embed.add_field(
                    name="Response:",
                    value="Scoreboard will not be cleared.")
        except asyncio.TimeoutError:
            embed.add_field(
                name="Response:",
                value="No Response given, scoreboard will not be cleared.")
        await message.edit(embed=embed)
        await message.clear_reactions()

    @commands.is_owner()
    @clear.command(name="player", autohelp=False)
    async def clear_player(self, ctx: commands.Context, player: Union[discord.Member, int]):
        """removes a particular player (or nonexistant id) from the scoreboard"""

        # if an ID was passed, try to get the user ID
        if isinstance(player, int):
            player_id = player
            player = ctx.guild.get_member(player_id)
            if not player:
                player_name = f"Unknown User (ID: {player_id})"
            else:
                player_name = player.name
        else:
            player_id = player.id
            player_name = player.name

        embed: discord.Embed = discord.Embed()

        embed.title = "Chess"
        embed.description = "Clear Player's Score"

        embed.add_field(
            name=f"Do you really want to remove Score for {player_name}?",
            value=f"This cannot be undone, <@{ctx.author.id}> respond below:")

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
                    value="Score has been removed.")
                await self.config.guild(ctx.guild).scoreboard.clear_raw(str(player_id))
            else:
                embed.add_field(
                    name="Response:",
                    value="Score will not be removed.")
        except asyncio.TimeoutError:
            embed.add_field(
                name="Response:",
                value="No Response given, score will not be removed.")
        await message.edit(embed=embed)
        await message.clear_reactions()
