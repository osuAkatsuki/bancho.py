# le dzifors
from cmyui.logging import log
from cmyui.logging import Ansi
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.objects.beatmap import Beatmap

import datetime

import app.state
import cmyui
import discord
import discordbot.botconfig as configb
import settings
from app.constants.mods import SPEED_CHANGING_MODS
from app.constants.privileges import Privileges
from app.objects.player import Player
from discord.ext import commands
from discord.utils import get
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_choice, create_option
from discordbot.utils import constants as dconst
from discordbot.utils import embed_utils as embutils
from discordbot.utils import slashcmd_options as sopt
from discordbot.utils import utils as dutils


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

        #* Reassign user and get player object
        user = user['user']
        player: Player = await app.state.sessions.players.from_cache_or_sql(name=user['name'])

        #* Check target user perms
        if Privileges.NORMAL not in player.priv and ctx.channel.id not in [
            configb.channels.gmt, configb.channels.admin]:
            return await ctx.send(embed=await embutils.emb_gen('permission_view_restrict'))

        #* Get mode and mods
        m = await dutils.getmodemods(user, mode, mods)
        if 'error' in m:
            return await ctx.send(embed=await embutils.emb_gen(m['error']))
        mode = m['mode']
        mods = m['mods']
        del(m)

        #* Get modestr and gulagmode with it's object and player stats
        modeobj = dconst.modemods2object[f"{mode}.{mods}"]
        stats = await dutils.getstats(player, mode, mods)

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
        
    #! dzifors code pls dont hit me
    
    @cog_ext.cog_slash(name="scores", description="Shows scores of player", options=sopt.scores)
    async def _scores(self, ctx: SlashContext, user:str=None, type:str=None, mode:str=None, mods:str="ignore", limit:str=None):
        if user == None:
            self_executed = True
        else:
            self_executed = False
        user = await dutils.getUser(ctx, "id, name, preferred_mode", user)
        #! Return if error occured
        if 'error' in user:
            cmyui.log(f"DISCORD BOT: {ctx.author} tried using /scores but got an error: {user['error']}", Ansi.RED)
            return await ctx.send(embed = await embutils.emb_gen(user['error']))
        
        if not type:
            type = "best"
        
        #TODO: i dont like this part but i dont got no idea on how to make it more clean without all this mess

        user = user['user']
        name = user['name']
        uid = user['id']
        
        # I totally did NOT copy this from the api, but anyways; this is the part where we set gamemode and mods
        if mode is None:
            mode = GameMode(user['preferred_mode'])
        else:
            mode = GameMode(int(mode))
        
        if mods is not None:
            if mods[0] in ("~", "="):  # weak/strong equality
                strong_equality = mods[0] == "="
                mods = mods[1:]
            else:  # use strong as default
                strong_equality = True

            if mods.isdecimal():
                # parse from int form
                mods = Mods(int(mods))
            else:
                # parse from string form
                mods = Mods.from_modstr(mods)
        
        player = await app.state.sessions.players.from_cache_or_sql(id = uid)

        #? build sql query & fetch info

        query = [
            "SELECT t.id, t.map_md5, t.score, t.pp, t.acc, t.max_combo, "
            "t.mods, t.n300, t.n100, t.n50, t.nmiss, t.ngeki, t.nkatu, t.grade, "
            "t.status, t.mode, t.play_time, t.time_elapsed, t.perfect "
            f"FROM {mode.scores_table} t "
            "INNER JOIN maps b ON t.map_md5 = b.md5 "
            "WHERE t.userid = :user_id AND t.mode = :mode_vn",
        ]

        params: dict[str, object] = {
            "user_id": player.id,
            "mode_vn": mode.as_vanilla,
        }

        if mods is not None:
            if strong_equality:  # type: ignore
                query.append("AND t.mods & :mods = :mods")
            else:
                query.append("AND t.mods & :mods != 0")

            params["mods"] = mods

        if type == "best":
            allowed_statuses = [2, 3]

            query.append("AND t.status = 2 AND b.status IN :statuses")
            params["statuses"] = allowed_statuses
            sort = "t.pp"
        else:
            sort = "t.play_time"

        query.append(f"ORDER BY {sort} DESC LIMIT :limit")
        try: 
            if limit is not None:
                if int(limit) > 100 or int(limit) < 1:
                    return await ctx.send(embed=await embutils.emb_gen("scores_over_limit"))
                else:
                    params["limit"] = int(limit)
            else:
                params["limit"] = 5
        except:
            return await ctx.send(embed=await embutils.emb_gen("not_integer"))

        rows = [
            dict(row)
            for row in await app.state.services.database.fetch_all(" ".join(query), params)
            
        ]

        #? fetch & return info from sql
        for row in rows:
            bmap = await Beatmap.from_md5(row.pop("map_md5"))
            row["beatmap"] = bmap.as_dict if bmap else None

        player_info = {
            "id": player.id,
            "name": player.name,
            "clan": {
                "id": player.clan.id,
                "name": player.clan.name,
                "tag": player.clan.tag,
            }
            if player.clan
            else None,
        }

        rows_real = {
            "scores": rows,
            "player": player_info
        }

        #TODO Again, maybe I'll fix that in the future but yeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeea
        #! Currently, the limit argument, will only select which best number is going to be displayed, when i learn Python, ill do it like it should be.
        username = user['name']
        score_count = len(rows_real['scores'])
        if not score_count:
            if self_executed:
                return await ctx.send(await embutils.emb_gen("no_scores_self"))
            else:
                return await ctx.send(
                    embed = discord.Embed(
                        title = f"No scores found for {username}",
                        description = f"{username} ain't got no scores. Tell them to set some and come back when they do.",
                        color = embutils.colors.red
                    )
                )

        if score_count != limit:
            if self_executed:
                await ctx.send(await embutils.emb_gen("not_enough_scores_self"))
            else:
                await ctx.send(
                    embed = discord.Embed(
                        title = f"{username} doesn't have enough scores!",
                        description = f"{username} doesn't have {limit} scores, but I will show you the score I found is the last, which is nr. {score_count}",
                        color = embutils.colors.red
                    )
                )

        
        return await ctx.send(
            embed = discord.Embed(
                title="This Worked",
                description=f"Your Arguments:\nplayer: {player}\nmode: {mode}\nmods: {params['mods']}\nlimit: {params['limit']}\nlimit check: {score_count}\nplayer info: {player_info}", 
                color=ctx.author.color
            )
        )



def setup(client):
    client.add_cog(osu(client))
