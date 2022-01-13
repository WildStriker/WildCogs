"""this module handles all initialization logic"""
import asyncio
import logging

LOGGER = logging.getLogger("red.wildcogs.chessgame")


class StartUp:
    """handles ChessGame's initialization"""

    def __init__(self):

        # for initialization functionality
        self._ready = asyncio.Event()
        self._init_task = None
        self._ready_raised = False

    def create_init_task(self):
        """creates initialize async task"""
        def _done_callback(task):
            """handles error occurence"""
            exc_info = task.exception()
            if exc_info is not None:
                LOGGER.error(
                    "An unexpected error occured during ChessGame's initialization",
                    exc_info=exc_info
                )
                self._ready_raised = True
            self._ready.set()

        self._init_task = asyncio.create_task(self.initialize())
        self._init_task.add_done_callback(_done_callback)

    async def initialize(self):
        """run any async tasks here before cog is ready for use"""
        await self._run_migrations()
        self._ready.set()
