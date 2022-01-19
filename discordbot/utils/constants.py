from app.constants.gamemodes import GameMode
mode_2_str = {
    0: "standard",
    1: "taiko",
    2: "catch",
    3: "mania"
}
mods2str = {
    "vn": "vanilla",
    "rx": "relax",
    "ap": "autopilot"
}

mode2gulag = {
    "0.vn": 0,
    "1.vn": 1,
    "2.vn": 2,
    "3.vn": 3,
    "0.rx": 4,
    "1.rx": 5,
    "2.rx": 6,
    "0.ap": 7,
}
gulag2mode = {
    0: 0,
    1: 1,
    2: 2,
    3: 3,
    4: 0,
    5: 1,
    6: 2,
    7: 0
}

modemods2object = {
    "0.vn": GameMode.VANILLA_OSU,
    "1.vn": GameMode.VANILLA_TAIKO,
    "2.vn": GameMode.VANILLA_CATCH,
    "3.vn": GameMode.VANILLA_MANIA,
    "0.rx": GameMode.RELAX_OSU,
    "1.rx": GameMode.RELAX_TAIKO,
    "2.rx": GameMode.RELAX_CATCH,
    "0.ap": GameMode.AUTOPILOT_OSU,
}

emotes = {
    "F": "<:rankf:853753898954391572>",
    "D": "<:rankd:853753898682155009>",
    "C": "<:rankc:853753898912448553>",
    "B": "<:rankb:853753899089657866>",
    "A": "<:ranka:853753899000004618>",
    "S": "<:ranks:853753899135402044>",
    "SH": "<:ranksh:853753899072094208>",
    "X": "<:rankx:853753898817028147>",
    "XH": "<:rankxh:853753899206311976>",
}

class colors:
    red = 0xe74c3c
    purple = 0x8e44ad