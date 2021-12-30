import app.state
import discord
from discord.ext import commands
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

async def getUser(ctx: commands.Context, user, to_select:str):
    if user == None: #Self usage
        user = await app.state.services.database.fetch_one(
            "SELECT osu_id FROM discord WHERE discord_id = :userself",
            {"userself": ctx.author.id}
        )
        if not user:
            return await ctx.send("You don't have your discord connected, type `.help link` for more info.")
        user = await app.state.services.database.fetch_one(
            f"SELECT {to_select} FROM users WHERE id = :id",
            {"id": user[0]}
        )
    elif len(user)<15: #Name on server
        user = await app.state.services.database.fetch_one(
            f"SELECT {to_select} FROM users WHERE name = :name",
            {"name": user}
        )
    else: #Mention
        user = user[3:-1]
        user = await app.state.services.database.fetch_one(
            "SELECT osu_id FROM discord WHERE discord_id = :mention",
            {"mention": user}
        )
        if not user:
            return await ctx.send('')
        user = await app.state.services.database.fetch_one(
            f"SELECT {to_select} FROM users WHERE id = :id",
            {"id": user[0]}
        )