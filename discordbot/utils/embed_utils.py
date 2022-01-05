import discord
from discord.ext import commands
import app.state.discordbot as dbot
import discordbot.botconfig as configb

prefix = configb.PREFIX
class colors:
    red = 0xe74c3c

embed_list = {
    "permission_view_restrict": {
        "title": "Error",
        "description": f"Only staff members can view profiles of restricted users.",
        "color": colors.red,
        "footer": "default"
    },
    "not_linked": {
        "title": "Error",
        "description": f"This user donesn't have their discord connected, you can always try with their username on server.",
        "color": colors.red,
        "footer": "default"
    },
    "not_linked_self": {
        "title": "Error",
        "description": f"You don't have your profile linked, type `{prefix}help link` to find out how to link your profile.",
        "color": colors.red,
        "footer": "default"
    },
    "usr_not_found": {
        "title": "Error",
        "description": f"Specified user doesn't exist, maybe you made a typo?.",
        "color": colors.red,
        "footer": "default"
    },
    "restricted_self": {
        "title": "Error",
        "description": f"You can't user this command because you're restricted.",
        "color": colors.red,
        "footer": "default"
    },
    "module_disabled": {
        "title": "Error",
        "description": f"This module has been disabled by administrator",
        "color": colors.red,
        "footer": "default"
    },
    "command_disabled": {
        "title": "Error",
        "description": f"This command has been disabled by administrator.",
        "color": colors.red,
        "footer": "default"
    },
    "cmd_admin_channel": {
        "title": "Error",
        "description": f"For security reasons, this command is aviable only in admin channels.",
        "color": colors.red,
        "footer": "default"
    },
    "rx_mania": {
        "title": "Error",
        "description": f"Relax can not be used with mania.",
        "color": colors.red,
        "footer": "default"
    },
    "ap_no_std": {
        "title": "Error",
        "description": f"Autopilot can be used only with standard.",
        "color": colors.red,
        "footer": "default"
    }
}
default_footer = f"Version {dbot.botversion} | Bot Creator: def750"
client = dbot.client

async def emb_gen(embed_name):
    """Fast preset embeds for quick use"""
    try:
        emb = embed_list[embed_name]
    except:
        raise IndexError('Embed not found')

    embed = discord.Embed(title=emb['title'], description=emb['description'], color=emb['color'])
    if emb['footer'] == "default":
        embed.set_footer(text=default_footer)

    return embed