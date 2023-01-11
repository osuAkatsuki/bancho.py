from __future__ import annotations

import asyncio
import inspect
import sys
import json
from multiprocessing import Event
from multiprocessing import Manager
from multiprocessing import Process

import app.logging
import app.state.sessions
from app.anticheat.pp_caps import *
from app.constants.privileges import Privileges
from app.logging import Ansi
from app.objects.score import Score

# You can create separate .py files containing more checks for a better hierarchy
# and import the methods directly here as seen above with the example
# from app.anticheat.pp_caps import *


class Anticheat:
    def __init__(self):
        # The multi processing queue is used as shared memory between
        # bancho.py and it's anticheat process to communicate the scores
        self.score_queue = Manager().Queue()

        # The event is used as a semaphore that is used to shutdown the child process
        self.event = Event()

        self.running = False

    def run(self):
        """Starts the child process of this anticheat instance"""

        if self.running:
            raise Exception("This anticheat instance is already running.")
        self.running = True

        p = Process(target=self.run_internal, args=(self.score_queue,))
        p.daemon = True
        p.start()

    def shutdown(self):
        """Releases the event semaphore to end the child process safely"""

        self.event.set()
        
        # We can already assume the child process will
        # shut down soon here since the semaphore was set
        self.running = False
        
    def encode(self, obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                obj[k] = self.encode(v)
            return obj
        if not isinstance(obj, (int, str, float)):
            return self.encode(obj.__dict__)
        

    async def enqueue_score(self, score: Score):
        """Enqueues the specified score into this Anticheat instance."""

        # check if the score is eligible for being checked
        if not await self.anticheat_check_preprocessor(score):
            return

        try:
            score_dict = self.encode(score)
            self.score_queue.put(json.dumps(score_dict))
        except Exception as e:
            app.logging.log(f"[anticheat] An error occured while trying to enqueue score {score}:", Ansi.RED)
            app.logging.log(f"[anticheat] {e}", Ansi.RED)

    def run_internal(self, score_queue):
        """Runs the internal anticheat loop, processing all scores from the queue."""

        app.logging.log("Started anticheat service.", Ansi.MAGENTA)

        try:

            # Loop as long as the semaphore has not been set
            while not self.event.is_set():

                print("waiting for score thing")
                score = score_queue.get()  # get() is blocking
                print("received score thing")
                asyncio.run(self.run_anticheat_checks(self, score))

        # The keyboard Interrupt has to be handled in the child process separately
        except KeyboardInterrupt:
            app.logging.log(
                "Shutting down anticheat service safely due to KeyboardInterrupt.",
                Ansi.MAGENTA,
            )

        app.logging.log("Stopped anticheat service.", Ansi.MAGENTA)

    async def anticheat_check_preprocessor(self, score: Score) -> bool:
        """Returns a bool whether the enqueued score is eligible for anticheat checks.
        
           This operation should not be expensive as it is being done before enqueuing the score.
        """

        if score.player.priv & Privileges.WHITELISTED:
            return False

        return True

    async def run_anticheat_checks(self, score: dict):
        """Runs the defined checks over the specified score and handles upon them"""

        # Get all imported functions TODO: Find a better solution for this as this
        #                                  technically uses all methods imported
        checks = dict(inspect.getmembers(sys.modules[__name__], inspect.isfunction))
        checks.pop("run_anticheat_checks")
        print(checks)
        return

        # Run each check and act upon it if necessary
        for (name, callable) in checks.items():
            result = await callable(score)
            if result:
                score.player.restrict(app.state.sessions.bot, result)
                app.logging.log(
                    f"{score.player} has been restricted through anticheat check '{name}' failing {score} (reason: {result})",
                    Ansi.CYAN,
                )

                return
