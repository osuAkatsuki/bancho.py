from datetime import datetime

import app.state
import discord
import settings
from app.constants.privileges import Privileges
from app.objects.player import Player
from cmyui.logging import log
from discord.ext import commands
from discord.utils import get
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_choice, create_option
from discordbot import botconfig as dconf
from discordbot.utils import constants as dconst
from discordbot.utils import embed_utils as embutils
from discordbot.utils import slashcmd_options as sopt
from discordbot.utils.embed_utils import emb_gen



class admin(commands.Cog):
    def __init__(self, client):
        self.client = client

    @cog_ext.cog_slash(name="restrict", description="Restrict user with specified reason.",
            options=sopt.restrict)
    async def _restrict(self, ctx: SlashContext, user=None, reason:str=None):
        #TODO: Send dm to user about restriction
        # Check author and it's perms
        a = await app.state.services.database.fetch_val(
            "SELECT osu_id FROM discord WHERE discord_id = :dscid",
            {"dscid": ctx.author.id})
        if not a:
            return await ctx.send(embed=await embutils.emb_gen('not_linked_self'))
        a = await app.state.services.database.fetch_one(
            "SELECT name, priv, country FROM users WHERE id = :oid",
            {"oid": a})
        if not a:
            return await ctx.send("Critical error no1")

        # Get users objects
        aobj: Player = await app.state.sessions.players.from_cache_or_sql(name=a['name'])
        t: Player = await app.state.sessions.players.from_cache_or_sql(name=user)

        # Check if author has admnin perms
        if Privileges.ADMINISTRATOR not in aobj.priv:
            return await ctx.send(embed=await embutils.emb_gen('no_perms_admin'))
        if ctx.channel_id != dconf.channels.admin:
            return await ctx.send(embed=await embutils.emb_gen('cmd_admin_channel'))
        # Check target
        if not t:
            return await ctx.send(embed=await embutils.emb_gen('usr_not_found'))
        if Privileges.NORMAL not in t.priv:
            return await ctx.send(embed=await embutils.emb_gen('alr_restricted'))

        #* Restrict target user
        await t.restrict(admin=aobj, reason=reason)

        #* Generate end send embed
        embed = discord.Embed(
            title=f"{t.name} got restricted!",
            color=dconst.colors.purple,
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="Player",
            value=f"[{t.name}](https://{settings.DOMAIN}/u/{t.id})",
            inline=True
        )
        embed.add_field(
            name="Admin",
            value=f"[{aobj.name}](https://{settings.DOMAIN}/u/{aobj.id})",
            inline=True
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text="shame", icon_url=aobj.avatar_url)
        embed.set_thumbnail(url=t.avatar_url)

        shame = ctx.guild.get_channel(dconf.channels.shame)
        logs = ctx.guild.get_channel(dconf.channels.logs)
        await logs.send(embed=embed)
        await shame.send(embed=embed)
        return await ctx.send(embed=embed)

    @cog_ext.cog_slash(name="unrestrict", description="Unrestrict user with specified reason.",
            options=sopt.restrict)
    async def _unrestrict(self, ctx: SlashContext, user=None, reason:str=None):
        #TODO: Send dm to user about unrestriction
        # Check author and it's perms
        a = await app.state.services.database.fetch_val(
            "SELECT osu_id FROM discord WHERE discord_id = :dscid",
            {"dscid": ctx.author.id})
        if not a:
            return await ctx.send(embed=await embutils.emb_gen('not_linked_self'))
        a = await app.state.services.database.fetch_one(
            "SELECT name, priv, country FROM users WHERE id = :oid",
            {"oid": a})
        if not a:
            return await ctx.send("Critical error no1")

        # Get users objects
        aobj: Player = await app.state.sessions.players.from_cache_or_sql(name=a['name'])
        t: Player = await app.state.sessions.players.from_cache_or_sql(name=user)

        # Check if author has admnin perms
        if Privileges.ADMINISTRATOR not in aobj.priv:
            return await ctx.send(embed=await embutils.emb_gen('no_perms_admin'))
        if ctx.channel_id != dconf.channels.admin:
            return await ctx.send(embed=await embutils.emb_gen('cmd_admin_channel'))
        # Check target
        if not t:
            return await ctx.send(embed=await embutils.emb_gen('usr_not_found'))
        if Privileges.NORMAL in t.priv:
            return await ctx.send(embed=await embutils.emb_gen('not_restricted'))

        #* Restrict target user
        await t.unrestrict(admin=aobj, reason=reason)

        #* Generate end send embed
        embed = discord.Embed(
            title=f"{t.name} got unrestricted!",
            color=dconst.colors.purple,
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="Player",
            value=f"[{t.name}](https://{settings.DOMAIN}/u/{t.id})",
            inline=True
        )
        embed.add_field(
            name="Admin",
            value=f"[{aobj.name}](https://{settings.DOMAIN}/u/{aobj.id})",
            inline=True
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text="yay", icon_url=aobj.avatar_url)
        embed.set_thumbnail(url=t.avatar_url)

        shame = ctx.guild.get_channel(dconf.channels.shame)
        logs = ctx.guild.get_channel(dconf.channels.logs)
        await logs.send(embed=embed)
        await shame.send(embed=embed)
        return await ctx.send(embed=embed)

    # @cog_ext.cog_slash(name = "silence", description = "Silence a user with specified reason and duration", options = sopt.silence)
    # async def _silence(self, ctx: SlashContext, user=None, duration:str=None, reason:str=None):
    #     #TODO: Send dm to user about unrestriction
    #     # Check author and it's perms
    #     a = await app.state.services.database.fetch_val(
    #         "SELECT osu_id FROM discord WHERE discord_id = :dscid",
    #         {"dscid": ctx.author.id})
    #     if not a:
    #        return await ctx.send(embed=await embutils.emb_gen('not_linked_self'))
    #     a = await app.state.services.database.fetch_one(
    #         "SELECT name, priv, country FROM users WHERE id = :oid",
    #         {"oid": a})
    #     if not a:
    #         return await ctx.send("Critical error no1")

    #     # Get users objects
    #     aobj: Player = await app.state.sessions.players.from_cache_or_sql(name=a['name'])
    #     t: Player = await app.state.sessions.players.from_cache_or_sql(name=user)

    #     # Check if author has admnin perms
    #     if Privileges.ADMINISTRATOR not in aobj.priv:
    #         return await ctx.send(embed=await embutils.emb_gen('no_perms_admin'))
    #     if ctx.channel_id != dconf.channels.admin:
    #         return await ctx.send(embed=await embutils.emb_gen('cmd_admin_channel'))
    #     # Check target
    #     if not t:
    #         return await ctx.send(embed=await embutils.emb_gen('usr_not_found'))

    #     await t.silence(admin=aobj, duration=duration, reason=reason)

    #     #* Generate end send embed
    #     embed = discord.Embed(
    #         title=f"{t.name} got silenced!",
    #         color=dconst.colors.purple,
    #         timestamp=datetime.utcnow()
    #     )
    #     embed.add_field(
    #         name="Player",
    #         value=f"[{t.name}](https://{settings.DOMAIN}/u/{t.id})",
    #         inline=True
    #     )
    #     embed.add_field(
    #         name="Admin",
    #         value=f"[{aobj.name}](https://{settings.DOMAIN}/u/{aobj.id})",
    #         inline=True
    #     )
    #     embed.add_field(name="Reason", value=reason, inline=False)
    #     embed.set_footer(text="Zamknij pizdĘ", icon_url=aobj.avatar_url)
    #     embed.set_thumbnail(url=t.avatar_url)

    #     shame = ctx.guild.get_channel(dconf.channels.shame)
    #     logs = ctx.guild.get_channel(dconf.channels.logs)
    #     await logs.send(embed=embed)
    #     await shame.send(embed=embed)
    #     return await ctx.send(embed=embed)

    #     ***Dzifors will finish this when he comes back home ***

    @cog_ext.cog_slash(name="addnotes", description="Adds a note to specified User.", options=sopt.addnote)
    async def _addnote(self, ctx: SlashContext, user=None, note_contents:str=None):
        # Check author and it's perms
        a = await app.state.services.database.fetch_val(
            "SELECT osu_id FROM discord WHERE discord_id = :dscid",
            {"dscid": ctx.author.id})
        if not a:
            return await ctx.send(embed=await embutils.emb_gen('not_linked_self'))
        a = await app.state.services.database.fetch_one(
            "SELECT name, priv, country FROM users WHERE id = :oid",
            {"oid": a})
        if not a:
            return await ctx.send("Critical error no1")

        # Get users objects
        aobj: Player = await app.state.sessions.players.from_cache_or_sql(name=a['name'])
        t: Player = await app.state.sessions.players.from_cache_or_sql(name=user)

        # Check if author has admnin perms
        if Privileges.ADMINISTRATOR not in aobj.priv:
            return await ctx.send(embed=await embutils.emb_gen('no_perms_admin'))
        if ctx.channel_id != dconf.channels.admin:
            return await ctx.send(embed=await embutils.emb_gen('cmd_admin_channel'))
        # Check target
        if not t:
            return await ctx.send(embed=await embutils.emb_gen('usr_not_found'))

        await app.state.services.database.execute(
            "INSERT INTO logs "
            "(`from`, `to`, `action`, `msg`, `time`) "
            "VALUES (:from, :to, :action, :msg, NOW())",
            {
                "from": aobj.id,
                "to": t.id,
                "action": "note",
                "msg": "".join(note_contents),
            },
        )

        #* Generate end send embed
        embed = discord.Embed(
            title=f"{t.name} got a note added to them!",
            color=dconst.colors.teal,
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="Player",
            value=f"[{t.name}](https://{settings.DOMAIN}/u/{t.id})",
            inline=True
        )
        embed.add_field(
            name="Admin",
            value=f"[{aobj.name}](https://{settings.DOMAIN}/u/{aobj.id})",
            inline=True
        )
        embed.add_field(name="Note content:", value=note_contents, inline=False)
        embed.set_footer(text="Piwo piwo lubie piwo", icon_url=aobj.avatar_url)
        embed.set_thumbnail(url=t.avatar_url)

        logs = ctx.guild.get_channel(dconf.channels.logs)
        await logs.send(embed=embed)
        return await ctx.send(embed=embed)

    @cog_ext.cog_slash(name="check_notes", description="Check notes of a selected Player.", options=sopt.checknotes)
    async def _checknotes(self, ctx: SlashContext, target=None, author=None, page=1):
        # Check author and it's perms
        a = await app.state.services.database.fetch_val(
            "SELECT osu_id FROM discord WHERE discord_id = :dscid",
            {"dscid": ctx.author.id})
        if not a:
            return await ctx.send(embed=await embutils.emb_gen('not_linked_self'))
        a = await app.state.services.database.fetch_one(
            "SELECT name, priv, country FROM users WHERE id = :oid",
            {"oid": a})
        if not a:
            return await ctx.send("Critical error no1")

        # Permission Checks
        apriv = int(a['priv']) # Author Privileges
        if not apriv & 12 and not apriv & 13:
            return await ctx.send(embed=await embutils.emb_gen('no_perms_gmt'))

        #Channel Check
        if ctx.channel.id not in [dconf.channels.gmt, dconf.channels.admin]:
            return await ctx.send(embed=await embutils.emb_gen('cmd_admin_channel'))

        # Syntax Checks
        if page != None:
            try:
                int(page)
            except ValueError:
                return await ctx.send(embed=await embutils.emb_gen('page_not_num'))
            #TODO: Calculate max page num
            if page < 1:
                page = 1

def setup(client):
    client.add_cog(admin(client))
