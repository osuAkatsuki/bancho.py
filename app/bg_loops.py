import asyncio
import time

from cmyui.logging import Ansi
from cmyui.logging import log

import app.packets
import app.state
import settings
from app.constants.privileges import Privileges

#Discordbot imports
import discordbot.botconfig as configb
import discord
from discord.ext import commands
from discord_slash import SlashCommand
import app.state.discordbot as dbot
from cmyui import Version
import os

#Website imports
import aiohttp
import orjson
from quart import Quart
from quart import render_template
from cmyui.logging import Ansi, log
import zenith.zconfig as zconf
from app.state import website as zglob
from hypercorn.asyncio import serve
from hypercorn.config import Config
__all__ = ("initialize_housekeeping_tasks",)

OSU_CLIENT_MIN_PING_INTERVAL = 300000 // 1000  # defined by osu!


async def initialize_housekeeping_tasks() -> None:
    """Create tasks for each housekeeping tasks."""
    loop = asyncio.get_running_loop()

    app.state.sessions.housekeeping_tasks.update(
        {
            loop.create_task(task)
            for task in (
                _remove_expired_donation_privileges(interval=30 * 60),
                _update_bot_status(interval=5 * 60),
                _disconnect_ghosts(interval=OSU_CLIENT_MIN_PING_INTERVAL // 3),
                #def750's xD moment
                _bot_runner(),
                _website()
            )
        },
    )


async def _remove_expired_donation_privileges(interval: int) -> None:
    """Remove donation privileges from users with expired sessions."""
    while True:
        if settings.DEBUG:
            log("Removing expired donation privileges.", Ansi.LMAGENTA)

        expired_donors = await app.state.services.database.fetch_all(
            "SELECT id FROM users "
            "WHERE donor_end <= UNIX_TIMESTAMP() "
            "AND priv & 48",  # 48 = Supporter | Premium
        )

        for expired_donor in expired_donors:
            p = await app.state.sessions.players.from_cache_or_sql(
                id=expired_donor["id"],
            )

            assert p is not None

            # TODO: perhaps make a `revoke_donor` method?
            await p.remove_privs(Privileges.DONATOR)
            await app.state.services.database.execute(
                "UPDATE users SET donor_end = 0 WHERE id = :id",
                {"id": p.id},
            )

            if p.online:
                p.enqueue(
                    app.packets.notification("Your supporter status has expired."),
                )

            log(f"{p}'s supporter status has expired.", Ansi.LMAGENTA)

        await asyncio.sleep(interval)


async def _disconnect_ghosts(interval: int) -> None:
    """Actively disconnect users above the
    disconnection time threshold on the osu! server."""
    while True:
        await asyncio.sleep(interval)
        current_time = time.time()

        for p in app.state.sessions.players:
            if current_time - p.last_recv_time > OSU_CLIENT_MIN_PING_INTERVAL:
                log(f"Auto-dced {p}.", Ansi.LMAGENTA)
                p.logout()


async def _update_bot_status(interval: int) -> None:
    """Reroll the bot's status, every `interval`."""
    while True:
        await asyncio.sleep(interval)
        app.packets.bot_stats.cache_clear()

async def _bot_runner() -> None:
    dbot.botversion = Version(2, 0, 1)
    intents = discord.Intents.all()
    #-> Define bot
    client = commands.Bot(command_prefix=configb.PREFIX, intents=intents, case_insensitive=True)
    slash = SlashCommand(client, sync_commands=True, debug_guild=829366482739003432, sync_on_cog_reload=True)
    dbot.client = client
    dbot.slash = slash

    #-> Cog loading
    for filename in os.listdir(f'{configb.PATH_TO_FILES}cogs'):
        filename1 = filename
        if filename.endswith('.py') and not filename.startswith('_'):
            print(f"[DISCORD BOT] Loading {filename1}...")
            client.load_extension(f'discordbot.cogs.{filename[:-3]}')
            print(f'[DISCORD BOT] Loaded {filename1}')

    @client.event
    async def on_ready() -> None:
        log("[DISCORD BOT] Bot logged in", Ansi.GREEN)
        log(f"Bot name: {client.user.name}")
        log(f"Bot ID: {client.user.id}")
        log(f"Bot Version: {dbot.botversion}\n")

    @client.command()
    async def rlc(ctx, cog):
        if ctx.author.id not in configb.BOT_OWNERS:
            return await ctx.send("You're not an owner")
        try:
            client.unload_extension(f'discordbot.cogs.{cog}')
            client.load_extension(f'discordbot.cogs.{cog}')
            log(f"[DISCORD BOT] {ctx.author.name}#{ctx.author.discriminator} reloaded cog {cog}", Ansi.YELLOW)
        except Exception as e:
            log(f"[DISCORD BOT] {ctx.author.name}#{ctx.author.discriminator} tried to reload cog {cog} but error occured", Ansi.YELLOW)
            log(e, Ansi.RED)
            return await ctx.send(f"Error occured while reloading cog\n```{e}```", delete_after=10)
        return await ctx.send("Reloaded Cog")

    @client.command()
    async def load(ctx, cog):
        if ctx.author.id not in configb.BOT_OWNERS:
            return await ctx.send("You're not an owner")
        try:
            client.load_extension(f'discordbot.cogs.{cog}')
            log(f"[DISCORD BOT] {ctx.author.name}#{ctx.author.discriminator} loaded cog {cog}", Ansi.YELLOW)
        except Exception as e:
            log(f"[DISCORD BOT] {ctx.author.name}#{ctx.author.discriminator} tried to load cog {cog} but error occured", Ansi.YELLOW)
            log(e, Ansi.RED)
            return await ctx.send(f"Error occured while loading cog\n```{e}```", delete_after=10)
        return await ctx.send("Loaded Cog")

    try:
        await client.start(configb.TOKEN)
    finally:
        await client.close()
        log('[DISCORD BOT] Bot Connection Closed', Ansi.RED)

async def _website() -> None:
    app = Quart(__name__, 
                template_folder='/opt/gulag/zenith/templates/',
                root_path='/opt/gulag/zenith/',
                static_folder='/opt/gulag/zenith/static/',
                instance_path='/opt/gulag/zenith/')

    version = Version(0, 0, 1)

    # used to secure session data.
    # we recommend using a long randomly generated ascii string.
    app.secret_key = zconf.secret_key

    @app.before_serving
    async def http_conn() -> None:
        zglob.http = aiohttp.ClientSession(json_serialize=orjson.dumps)
        log('ZENITH: Got our Client Session!', Ansi.LGREEN)

    # globals which can be used in template code
    _version = repr(version)
    @app.before_serving
    @app.template_global()
    def appVersion() -> str:
        return _version

    _app_name = zconf.app_name_short
    @app.before_serving
    @app.template_global()
    def appName() -> str:
        return _app_name

    _app_name_l = zconf.app_name_long
    @app.before_serving
    @app.template_global()
    def appNameLong() -> str:
        return _app_name_l

    _captcha_key = zconf.hCaptcha_sitekey
    @app.before_serving
    @app.template_global()
    def captchaKey() -> str:
        return _captcha_key

    _domain = zconf.domain
    @app.before_serving
    @app.template_global()
    def domain() -> str:
        return _domain

    from zenith.blueprints.frontend import frontend
    app.register_blueprint(frontend)
    from zenith.blueprints.api import api
    app.register_blueprint(api, url_prefix="/wapi")
    
    @app.errorhandler(404)
    async def page_not_found(e):
        # NOTE: we set the 404 status explicitly
        return (await render_template(f'errors/404.html'), 404)



    #app.run(debug=zconf.debug) # blocking call
    def getappobj():
        return app
    if __name__ == "app.bg_loops":
        await serve(app, Config(), shutdown_trigger=lambda: asyncio.Future())
        