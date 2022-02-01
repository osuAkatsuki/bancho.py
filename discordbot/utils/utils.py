from app.objects.player import Player
import app.state
import discord
from discord.ext import commands
from app.commands import str_priv_dict
from discordbot.utils import constants as dconst
from app.constants.privileges import Privileges

import discordbot.utils.embed_utils as embutils
def argparse(args:list, allowed_args:list):
    """Parse list of non-positional arguments and return a dictionary"""
    dic = {}
    current_key = None
    for el in args:
        if el in allowed_args:
            current_key = el
            dic[current_key] = []
        else:
            dic[current_key].append(el)

    for key, val in dic.items():
        dic[key] = " ".join(val)

async def getUser(ctx: commands.Context, to_select:str, user):
    async with app.state.services.database.connection() as db_conn:
        """Gets user from database using discord's context."""
        if user == None: #Self usage
            user = await app.state.services.database.fetch_val(
                "SELECT osu_id FROM discord WHERE discord_id = :userself",
                {"userself": ctx.author.id}
            )
            if not user:
                return {"error": "not_linked_self"}
            user = await app.state.services.database.fetch_one(
                f"SELECT {to_select} FROM users WHERE id = :id",
                {"id": user}
            )
            self_exec = True
        elif len(user)<15: #Name on server
            user = await app.state.services.database.fetch_one(
                f"SELECT {to_select} FROM users WHERE name = :name",
                {"name": user}
            )
            if not user:
                return {"error": "usr_not_found"}
            discord:int = await app.state.services.database.fetch_val(
                "SELECT discord_id FROM discord WHERE osu_id = :oid",
                {"oid": user[0]}
            )
            if not discord:
                self_exec = False
            elif ctx.author.id == int(discord):
                self_exec = True
            else:
                self_exec = False
        else: #Mention
            user = user[3:-1]
            user = await app.state.services.database.fetch_val(
                "SELECT osu_id FROM discord WHERE discord_id = :mention",
                {"mention": user}
            )
            if not user:
                return {"error": "not_linked"}
            if int(user) == ctx.author.id:
                self_exec = True
            else:
                self_exec = False
            user = await app.state.services.database.fetch_one(
                f"SELECT {to_select} FROM users WHERE id = :id",
                {"id": user}
            )
        #Convert to dict for easier usage
        user = dict(user)
        return {"user": user, "self_exec": self_exec}

def convert_rx(mode: int, rx: int) -> int:
    if mode == 3:
        return 3

    if rx == "rx":
        return mode + 4

    if rx == "ap":
        return 8

    return mode


def getprivlist(player: Player, format:str=""):
    priv_list = [
        priv.name for priv in Privileges if player.priv & priv and bin(priv).count("1") == 1
    ][::-1]
    str = ""
    if player.id in [3,4]:
        str += format + "Owner" + format + " "
    for el in priv_list:
        str += format + el.capitalize() + format + " "

    return str

async def checkperms(ctx: commands.Context, perms:list):
    # Check author and it's perms
    a = await app.state.services.database.fetch_val(
        "SELECT osu_id FROM discord WHERE discord_id = :dscid",
        {"dscid": ctx.author.id})
    if not a:
        return {"error": "not_linked_self"}
    a = await app.state.services.database.fetch_one(
        "SELECT name, priv, country FROM users WHERE id = :oid",
        {"oid": a})
    if not a:
        return {"error": "discord_no_osu"}
    a = dict(a)

    # Check perms
    success_checks = 0
    for x in perms:
        if x in Privileges(int(a['priv'])):
            success_checks += 1

    if success_checks > 0:
        return {"author": a}
    else:
        return {"error": 'no_perms'}

async def getmodemods(user:dict, mode, mods:str):
    if not mode:
        mode = user['preferred_mode'] if user['preferred_mode'] else 0 #Cleanup by tsunyoku, thx <3
    if not mods:
        mods = "vn"
    else:
        if mods == "rx" and mode == 3:
            return {'error':'rx_mania'}
        elif mods == "ap" and mode != 0:
            return {'error':'ap_no_std'}
    
    return {'mode': mode, 'mods': mods}

async def getstats(player: Player, mode, mods):
    stats = await app.state.services.database.fetch_one(
    "SELECT * FROM stats WHERE id = :uid AND mode = :mode",
    {"uid": player.id, "mode": dconst.mode2gulag[f"{mode}.{mods}"]})
    return dict(stats)