"""cog to play chess in discord"""
import asyncio
import io
import logging
from typing import Dict, Union

import discord
import jsonpickle
from redbot.core import Config, commands

from .commands import MainCommands, PlayerCommands, ScoreboardCommands
from .constants import DEFAULT_ELO, LATEST_SCHEMA_VERSION
from .game import Game

LOGGER = logging.getLogger("red.wildcogs.chessgame")

# type hints
Games = Dict[str, Game]


class ChessGame(commands.Cog,
                MainCommands,
                PlayerCommands,
                ScoreboardCommands):
    """Cog to Play chess!"""

    def __init__(self):
        super().__init__()

        self.config: Config = Config.get_conf(
            self,
            identifier=51314929031968350236701571200827144869558993811,
            force_registration=True)

        # ideally schema_version should default to LATEST_SCHEMA_VERSION
        # since this did not exist in the initial version this will be set to 0
        # until support is removed (_run_migration_v1)
        self.config.register_global(schema_version=0)

        self.config.register_guild(scoreboard={})

        self.config.register_channel(games={})

    def cog_unload(self):
        """clean up when cog is unloaded"""
        if self.startup.init_task is not None:
            self.startup.init_task.cancel()

    async def cog_before_invoke(self, ctx):
        """wait until cog is ready before running commands"""
        async with ctx.typing():
            await self.startup.ready.wait()
        if self.startup.ready_raised:
            await ctx.send(
                "There was an error during ChessGame's initialization."
                " Check logs for > more information."
            )
            raise commands.CheckFailure()

    async def _get_games(self, channel) -> Games:
        config_games = await self.config.channel(channel).games()
        if not config_games:
            return None

        games = {}
        for game_name in config_games:
            game = jsonpickle.decode(config_games[game_name])
            games[game_name] = game

        return games

    async def _get_game(self, channel, game_name: str) -> Game:
        game_json = await self.config.channel(channel).games.get_raw(game_name)
        game = jsonpickle.decode(game_json)
        return game

    async def _set_game(self, channel, game_name: str, game: Game):
        game_json = jsonpickle.encode(game)
        await self.config.channel(channel).games.set_raw(game_name, value=game_json)

    async def _start_game(self, ctx: commands.Context,
                          player_black: discord.Member, player_white: discord.Member,
                          game_name: str = None, game_type: str = None):
        # get games config
        games = await self.config.channel(ctx.channel).games()
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

    async def _increment_score(self,
                               guild,
                               player_id: Union[int, str],
                               elo: int,
                               wins: int,
                               losses: int,
                               ties: int):
        player_id = str(player_id)
        async with self.config.guild(guild).scoreboard() as scoreboard:
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


class StartUp:
    """handles ChessGame's initialization"""

    def __init__(self):
        self.cog = None
        # for initialization functionality
        self.ready = asyncio.Event()
        self.init_task = None
        self.ready_raised = False

    def create_init_task(self, cog: commands.Cog):
        """creates initialize async task"""
        self.cog = cog

        def _done_callback(task):
            """handles error occurence"""
            exc_info = task.exception()
            if exc_info is not None:
                LOGGER.error(
                    "An unexpected error occured during ChessGame's initialization",
                    exc_info=exc_info
                )
                self.ready_raised = True
            self.ready.set()

        self.init_task = asyncio.create_task(self.initialize())
        self.init_task.add_done_callback(_done_callback)

    async def initialize(self):
        """run any async tasks here before cog is ready for use"""
        await self._run_migrations()
        self.ready.set()

    async def _run_migrations(self):
        """run migrations on existig data required for this cog to work"""
        schema_version = await self.cog.config.schema_version()

        # no updates required
        if schema_version == LATEST_SCHEMA_VERSION:
            return

        LOGGER.info("Running required migrations...")
        migrations = [
            self._run_migration_v1,
        ]
        while schema_version < LATEST_SCHEMA_VERSION:
            schema_version += 1
            LOGGER.info("Running migration_v%s", schema_version)
            await migrations[schema_version - 1]()
            await self.cog.config.schema_version.set(schema_version)
        LOGGER.info("Migration completed")

    async def _run_migration_v1(self):
        channels = await self.cog.config.all_channels()

        for channel, data in channels.items():
            old_games = jsonpickle.decode(data["games"])

            new_games = {}
            for key, game in old_games.items():
                new_games[key] = jsonpickle.encode(game)

            await self.cog.config.channel_from_id(channel).games.set(new_games)
