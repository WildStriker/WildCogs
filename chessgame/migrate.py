"""module will handle any required config migrations from previous schema versions"""
import logging

import jsonpickle

from .constants import LATEST_SCHEMA_VERSION

LOGGER = logging.getLogger("red.wildcogs.chessgame")


class Migrate:
    """handles ChessGame's migrations"""
    async def _run_migrations(self):
        """run migrations on existig data required for this cog to work"""
        schema_version = await self._config.schema_version()

        # no updates required
        if schema_version == LATEST_SCHEMA_VERSION:
            return

        LOGGER.info("Running required migrations")
        migrations = [
            self._run_migration_v1,
        ]
        while schema_version < LATEST_SCHEMA_VERSION:
            schema_version += 1
            LOGGER.info("Running migration_v%s", schema_version)
            await migrations[schema_version - 1]()
            await self._config.schema_version.set(schema_version)
        LOGGER.info("Migration completed")

    async def _run_migration_v1(self):
        channels = await self._config.all_channels()

        for channel, data in channels.items():
            old_games = jsonpickle.decode(data["games"])

            new_games = {}
            for key, game in old_games.items():
                new_games[key] = jsonpickle.encode(game)

            await self._config.channel_from_id(channel).games.set(new_games)
