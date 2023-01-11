from __future__ import annotations

import inspect
import sys
import asyncio
import app.logging
import app.state.sessions

from typing import Optional
from app.logging import Ansi
from multiprocessing import Process, Event, Manager, Queue
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.constants.privileges import Privileges
from app.objects.player import Player
from app.objects.score import Score
# DO NOT import non-anticheat check functions directly, it'll mess up inspect.getmembers
# You can create separate .py files containing more checks for a better hierarchy.


class Anticheat:

    manager = Manager()
    score_queue = manager.Queue()
    event = Event()
    running = False


    @classmethod
    def enqueue_score(self, score: Score):
        self.score_queue.put(score)
    
    
    @classmethod
    async def run_anticheat_checks(self, score: Score):
        checks = dict(inspect.getmembers(sys.modules[__name__], inspect.isfunction))
        checks.pop("run_anticheat_checks")
        print(checks)
        return
    
        if not anticheat_check_preprocessor(score):
            return
        
        for (name, callable) in checks.items():
            result = await callable(score)
            if result:
                score.player.restrict(app.state.sessions.bot, result)
                app.logging.log(
                    f"{score.player} has been restricted through anticheat check '{name}' failing {score} (reason: {result})",
                    Ansi.CYAN,
                )
                
    
    @classmethod
    async def anticheat_check_preprocessor(self, score: Score) -> bool:
        """Returns a bool whether the enqueued score is eligible for anticheat checks."""
        
        if score.player.privs & Privileges.WHITELISTED:
            return False
        
        return True
                

    @classmethod
    def run(self):
        self.p = Process(target=self.run_internal, args=(self.score_queue,))
        self.p.daemon = True
        self.p.start()
        
        
    @classmethod
    def shutdown(self):
        self.event.set()
        
        
    @classmethod
    def run_internal(self, score_queue):
        
        app.logging.log(
            "Started anticheat service.",
            Ansi.MAGENTA
        )
        
        try:
            
            while not self.event.is_set():
                print("waiting for score thing")
                score = score_queue.get()
                print("received score thing")
                asyncio.run(self.run_anticheat_checks(self, score))
                
        except KeyboardInterrupt:
            app.logging.log(
                "Shutting down anticheat service safely due to KeyboardInterrupt.",
                Ansi.MAGENTA
            )
            
        app.logging.log(
            "Stopped anticheat service.",
            Ansi.MAGENTA
        )
        
