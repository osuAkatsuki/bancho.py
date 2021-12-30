import databases
import discord
from discord.ext import commands
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_commands import create_option, create_choice

import cmyui
import datetime

from app.constants.mods import SPEED_CHANGING_MODS
from app.constants.privileges import Privileges
from app.objects.player import Player
import app.state
from app.state import services

from discordbot.utils import utils as dutils
from discordbot.utils import embed_utils as embutils
import discordbot.botconfig as configb

class osu(commands.Cog):
    def __init__(self, client):
        self.client = client

    @cog_ext.cog_slash(name="profile", description="Check user profile in specified mode with specfied mods.",
            options=[
                create_option(
                    name="user",
                    description="Select user.",
                    option_type=3,
                    required=False,
                ),
                create_option(
                    name="mode",
                    description="Select mode.",
                    option_type=3,
                    required=False,
                    choices=[
                        create_choice(
                            name="Standard",
                            value="0"
                        ),
                        create_choice(
                            name="Taiko",
                            value="1"
                        ),
                        create_choice(
                            name="Catch",
                            value="2"
                        ),
                        create_choice(
                            name="Mania",
                            value="3"
                        ),
                    ]
                ),
                create_option(
                    name="mods",
                    description="Select mods.",
                    option_type=3,
                    required=False,
                    choices=[
                        create_choice(
                            name="Vanilla",
                            value="vn"
                        ),
                        create_choice(
                            name="Relax",
                            value="rx"
                        ),
                        create_choice(
                            name="Autopilot",
                            value="ap"
                        )
                    ]
                )
            ]
        )
    async def _profile(self, ctx: SlashContext, user:str=None, mode:str=None, mods:str=None):
        #* Permission and access checks
        for role in ctx.author.roles:           #getting all roles of member
            if role.id == int(configb.ROLES['restricted']):
                #? THIS CODE CHECKS FOR ROLE, NOT PERMS
                return await ctx.send(embed=await embutils.emb_gen("restricted_self"))

        #* Get user
        async with app.state.services.database.connection() as db_conn:
            to_select = "id, name, country, priv, creation_time, latest_activity, clan_id, clan_priv"
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
                if not user:
                    return await ctx.send('User not found error')
            else: #Mention
                user = user[3:-1]
                user = await app.state.services.database.fetch_one(
                    "SELECT osu_id FROM discord WHERE discord_id = :mention",
                    {"mention": user}
                )
                if not user:
                    return await embutils.emb_gen('usr_not_found')
                user = await app.state.services.database.fetch_one(
                    f"SELECT {to_select} FROM users WHERE id = :id",
                    {"id": user[0]}
                )
            #Convert to dict for easier usage
            user = dict(user)
        if not user:
            return await embutils.emb_gen('not_linked')
        async with app.state.services.database.connection() as db_conn:
            pass
        return await ctx.send(f"{user=} {mode=} {mods=}")

def setup(client):
    client.add_cog(osu(client))
