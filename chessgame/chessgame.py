"""cog to play chess in discord"""
import logging

from redbot.core import Config, commands

from .commands import MainCommands, PlayerCommands
from .migrate import Migrate
from .startup import StartUp
from .util import Util

LOGGER = logging.getLogger("red.wildcogs.chessgame")


class ChessGame(commands.Cog,
                StartUp,
                Migrate,
                Util,
                MainCommands,
                PlayerCommands):
    """Cog to Play chess!"""

    def __init__(self):
        super().__init__()

        self._config = Config.get_conf(
            self,
            identifier=51314929031968350236701571200827144869558993811,
            force_registration=True)

        # ideally schema_version should default to LATEST_SCHEMA_VERSION
        # since this did not exist in the initial version this will be set to 0
        # until support is removed (_run_migration_v1)
        self._config.register_global(schema_version=0)

        self._config.register_channel(games={})

    def cog_unload(self):
        """clean up when cog is unloaded"""
        if self._init_task is not None:
            self._init_task.cancel()

    async def cog_before_invoke(self, ctx):
        """wait until cog is ready before running commands"""
        async with ctx.typing():
            await self._ready.wait()
        if self._ready_raised:
            await ctx.send(
                "There was an error during ChessGame's initialization."
                " Check logs for > more information."
            )
            raise commands.CheckFailure()
