from __future__ import annotations

import asyncio
import inspect
import sys
from multiprocessing import Event
from multiprocessing import Manager
from multiprocessing import Process

import app.logging
import app.state.sessions
from app.constants.privileges import Privileges
from app.logging import Ansi
from app.objects.score import Score

# You can create separate .py files containing more checks for a better hierarchy
# and import the methods directly here, like shown in the example below.
from app.anticheat.pp_caps import *


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
        self.running = False # We can already assume the child process will
                             # shut down soon here since the semaphore was set


    def run_internal(self, score_queue):
        """Runs the internal anticheat loop, processing all scores from the queue."""

        app.logging.log("Started anticheat service.", Ansi.MAGENTA)

        try:

            # Loop as long as the semaphore has not been set
            while not self.event.is_set():
                
                print("waiting for score thing")
                score = score_queue.get() # get() is blocking
                print("received score thing")
                asyncio.run(self.run_anticheat_checks(self, score))

        # The keyboard Interrupt has to be handled in the child process separately
        except KeyboardInterrupt:
            app.logging.log(
                "Shutting down anticheat service safely due to KeyboardInterrupt.",
                Ansi.MAGENTA,
            )

        app.logging.log("Stopped anticheat service.", Ansi.MAGENTA)


    def enqueue_score(self, score: Score):
        """Enqueues the specified score into this Anticheat instance."""
        
        # check if the score is eligible for being checked
        if not self.anticheat_check_preprocessor(score):
            return
        
        self.score_queue.put(score)
        

    async def anticheat_check_preprocessor(self, score: Score) -> bool:
        """Returns a bool whether the enqueued score is eligible for anticheat checks."""

        if score.player.privs & Privileges.WHITELISTED:
            return False

        return True


    async def run_anticheat_checks(self, score: Score):
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