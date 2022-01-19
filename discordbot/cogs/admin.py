import discord
from discord.ext import commands
from discord.utils import get
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_choice, create_option
from app.objects.player import Player
from discordbot.utils import slashcmd_options as sopt
import app.state


class admin(commands.Cog):
    def __init__(self, client):
        self.client = client

    @cog_ext.cog_slash(name="restrict", description="Restrict user with specified reason.",
            options=sopt.restrict)
    async def _restrict(self, ctx: SlashContext, user=None, reason:str=None):
        # Check author and it's perms
        a = await app.state.services.database.fetch_val(
            "SELECT osu_id FROM discord WHERE discord_id = :dscid",
            {"dscid": ctx.author.id})
        if not a:
            return await ctx.send("Error no1")
        a = await app.state.services.database.fetch_one(
            "SELECT name, priv, country FROM users WHERE id = :oid",
            {"oid": a})
        if not a:
            return await ctx.send("Critical error no1")

        # Get users objects
        aobj: Player = await app.state.sessions.players.from_cache_or_sql(name=a['name'])
        t: Player = await app.state.sessions.players.from_cache_or_sql(name=user)
        if not t:
            return await ctx.send("Error no2")
        return await ctx.send(f"{t=} {aobj=}")

def setup(client):
    client.add_cog(admin(client))