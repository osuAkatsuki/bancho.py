import datetime
import os
import aiohttp
import app.state
import app.state.discordbot as dbot
import cmyui
import discord
import discordbot.botconfig as configb
import settings
from app.constants.privileges import Privileges
from app.objects.player import Player
from discord.ext import commands
from discord.utils import get
from discord_slash import SlashContext, cog_ext
from discordbot.utils import constants as dconst

session = aiohttp.ClientSession()
class misc(commands.Cog):
    def __init__(self, client):
        self.client = client
    
    @cog_ext.cog_slash(name="status", description="Check server status")
    async def _profile(self, ctx: SlashContext):
        #* Pings
        st = ""
        async with session.get(f"https://c.{settings.DOMAIN}/") as r:
            if r.status == 200:
                st += f"\n▸ **Bancho** {dconst.emotes['online']}"
            else:
                st += f"\n▸ **Bancho** {dconst.emotes['offline']}"
            del(r)
        async with session.get(f"https://a.{settings.DOMAIN}/1") as r:
            if r.status == 200:
                st += f"\n▸ **Avatar Server** {dconst.emotes['online']}"
            else:
                st += f"\n▸ **Avatar Server** {dconst.emotes['offline']}"
            del(r)
        async with session.get(f"https://api.{settings.DOMAIN}/") as r:
            if r.status == 200:
                st += f"\n▸ **API** {dconst.emotes['online']}"
            else:
                st += f"\n▸ **API** {dconst.emotes['offline']}"
            del(r)
        async with session.get(f"http://localhost:8000/") as r:
            if r.status == 200:
                st += f"\n▸ **Website** {dconst.emotes['online']}"
            else:
                st += f"\n▸ **Website** {dconst.emotes['offline']}"
            del(r)
        st += "\n▸ **Bot:** " + dconst.emotes['online']

        #Embed
        embed = discord.Embed(
            title="Server status",
            description=f"▸ **Users Online:** {len(app.state.sessions.players.unrestricted) - 1}\n" + st,
            color=dconst.colors.blue
        )
        return await ctx.send(embed=embed)

def setup(client):
    client.add_cog(misc(client))
