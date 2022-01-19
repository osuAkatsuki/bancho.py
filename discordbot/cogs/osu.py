import datetime
from asyncio.proactor_events import constants

import app.state
import cmyui
import databases
import discord
import settings
import discordbot.botconfig as configb
from app.constants.mods import SPEED_CHANGING_MODS
from app.constants.privileges import Privileges
from app.objects.player import Player
from app.state import services
from discord.ext import commands
from discord.utils import get
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_choice, create_option
from discordbot.utils import constants as dconst
from discordbot.utils import embed_utils as embutils
from discordbot.utils import utils as dutils
from discordbot.utils import slashcmd_options as sopt


class osu(commands.Cog):
    def __init__(self, client):
        self.client = client

    @cog_ext.cog_slash(name="profile", description="Check user profile in specified mode with specfied mods.",
            options=sopt.profile
        )
    async def _profile(self, ctx: SlashContext, user:str=None, mode:str=None, mods:str=None, size:str="basic"):
        #* Permission and access checks
        for role in ctx.author.roles:           #getting all roles of member
            if role.id == int(configb.ROLES['restricted']):
                #? THIS CODE CHECKS FOR ROLE, NOT PERMS
                return await ctx.send(embed=await embutils.emb_gen("restricted_self"))


        #* Get user
        user = await dutils.getUser(ctx, "id, name, country, preferred_mode, creation_time, latest_activity", user)

        #! Return if error occured
        if 'error' in user:
            return await ctx.send(embed=await embutils.emb_gen(user['error']))

        #* Reassign user
        user = user['user']

        #* Get player object
        player: Player = await app.state.sessions.players.from_cache_or_sql(name=user['name'])


        #* Get mode and mods
        if not mode:
            mode = user['preferred_mode'] if user['preferred_mode'] else 0 #Cleanup by tsunyoku, thx <3

        if not mods:
            mods = "vn"
        else:
            if mods == "rx" and mode == 3:
                return await ctx.send(embed=await embutils.emb_gen('rx_mania'))
            elif mods == "ap" and mode != 0:
                return await ctx.send(embed= await embutils.emb_gen('ap_no_std'))


        #* Get modestr and gulagmode with it's object
        modeobj = dconst.modemods2object[f"{mode}.{mods}"]

        #* Get player stats
        stats = await app.state.services.database.fetch_one(
            "SELECT * FROM stats WHERE id = :uid AND mode = :mode",
            {"uid": player.id, "mode": dconst.mode2gulag[f"{mode}.{mods}"]})
        stats = dict(stats)

        #TODO: Get player status and convert it
        status = player.status

        #TODO: Calculate player's level

        #! Assign vars and send embed
        #* Value reassignment
        author_name = f"{user['name']}'s Profile In osu!{dconst.mode_2_str[int(mode)].capitalize()}"
        if mods != "vn":
            author_name += f" with {dconst.mods2str[mods].capitalize()}"

        #TODO: Fix it, currently displays weird time format (Ex.: 1 day, 13:17:27)
        playtime = datetime.timedelta(seconds=stats['playtime'])

        embed = discord.Embed(
            color=ctx.author.color,
        )
        embed.set_author(
            name=author_name,
            icon_url=f"https://{settings.DOMAIN}/static/images/flags/{user['country'].upper()}.png",
            url=f"https://{settings.DOMAIN}/u/{player.id}"
        )
        embed.set_thumbnail(
            url=f"https://a.{settings.DOMAIN}/{player.id}"
        )
        embed.add_field(
            name="Stats",
            value=f"▸ **Global Rank:** {await player.get_global_rank(modeobj)} "
                  f"**Country Rank:** {await player.get_country_rank(modeobj)}\n"
                  f"▸ **PP:** {stats['pp']} **ACC:** {stats['acc']}\n"
                  f"▸ **Max Combo:** {stats['max_combo']}\n"
                  f"▸ **Ranked Score:** {stats['rscore']:,} "
                  f"▸ **Total Score:** {stats['tscore']:,}\n"
                  f"▸ **Playcount:** {stats['plays']} **Playtime:** {playtime}\n"
                  f"▸ **Ranks:** {dconst.emotes['XH']} `{stats['xh_count']}` "
                  f"{dconst.emotes['X']} `{stats['x_count']}` {dconst.emotes['SH']} "
                  f"`{stats['sh_count']}` {dconst.emotes['S']} `{stats['s_count']}` "
                  f"{dconst.emotes['A']} `{stats['a_count']}`",
            inline=False
        )
        if size=="full":
            register_date = datetime.datetime.fromtimestamp(int(user['creation_time'])).strftime("%m.%d.%Y %H:%M:%S")
            last_seen = datetime.datetime.fromtimestamp(int(user['latest_activity'])).strftime("%m.%d.%Y %H:%M:%S")
            embed.add_field(
                name="User Information",
                value=f"▸ **User ID:** {player.id}\n"
                      f"▸ **User groups:** {dutils.getprivlist(player, '`')}\n"
                      f"▸ **Registration date:** {register_date}\n"
                      f"▸ **Last seen date:** {last_seen}",
                inline=False
            )
        return await ctx.send(embed=embed)

def setup(client):
    client.add_cog(osu(client))
