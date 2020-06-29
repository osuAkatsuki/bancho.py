from objects.player import Player
from constants import Privileges

class Channel:
    def __init__(self, *args, **kwargs) -> None:
        self.name = kwargs.get('name', None)
        self.topic = kwargs.get('topic', None)
        self.players = []

        self.read = kwargs.get('read', Privileges.Verified)
        self.write = kwargs.get('write', Privileges.Verified)
        self.auto_join = kwargs.get('auto_join', True)

    def join(self, p: Player) -> bool:
        if not p.priv & self.read:
            return False

        self.players.append(p)
        return True

    def leave(self, p: Player) -> None:
        self.players.remove(p)
