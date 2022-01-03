import databases
import discord
from discord.ext import commands
from discord.utils import get
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
from discordbot.utils import constants as dconst
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
        user = await dutils.getUser(
            ctx, "id, name, country, priv, creation_time, "
            "latest_activity, clan_id, clan_priv", user)
        #! Return if error occured
        if 'error' in user:
            return await ctx.send(embed=await embutils.emb_gen(user['error']))

        #* Conversion and syntax checks for mode
        if mode != None:
            modestr = dconst.mode_2_str[mode]
        else:
            #Get mode default from user's discord
            async with app.state.services.database.connection() as db_conn:
                mode = await app.state.services.database.fetch_val(
                    "SELECT default_mode FROM discord WHERE osu_id = :oid",
                    {"oid": user['user']['id']}
                )
                if not mode:
                    mode = 0
                print(mode)
        return await ctx.send(f"{user=} {mode=} {mods=}")

def setup(client):
    client.add_cog(osu(client))
