from __future__ import annotations

import app.packets
from app import usecases
from app.objects.menu import Menu
from app.objects.menu import MenuCommands
from app.objects.menu import MenuFunction
from app.objects.player import Player

# # temporary menu-related stuff
# async def bot_hello(p: Player) -> None:
#     p.send_bot(f"hello {p.name}!")


async def notif_hello(p: Player) -> None:
    p.enqueue(app.packets.notification(f"hello {p.name}!"))


MENU2 = Menu(
    "Second Menu",
    {
        usecases.menus.menu_keygen(): (MenuCommands.Back, None),
        usecases.menus.menu_keygen(): (
            MenuCommands.Execute,
            MenuFunction("notif_hello", notif_hello),
        ),
    },
)

MAIN_MENU = Menu(
    "Main Menu",
    {
        # usecases.menus.menu_keygen(): (MenuCommands.Execute, MenuFunction("bot_hello", bot_hello)),
        usecases.menus.menu_keygen(): (
            MenuCommands.Execute,
            MenuFunction("notif_hello", notif_hello),
        ),
        usecases.menus.menu_keygen(): (MenuCommands.Advance, MENU2),
    },
)
