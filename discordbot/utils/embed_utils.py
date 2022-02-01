import discord
from discord.ext import commands
import app.state.discordbot as dbot
import discordbot.botconfig as configb
from discordbot.utils.constants import colors

prefix = configb.PREFIX


default_footer = f"Version {dbot.botversion} | Bot Creator: def750"
client = dbot.client

async def emb_gen(embed_name, args=None):
    embed_list = {
        "permission_view_restrict": {
            "title": "Error",
            "description": f"Due to security reasons, viewing profiles of restricted users is only available in staff channels.",
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
            "description": f"For security reasons, this command is available only in admin channels.",
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
        },
        "alr_restricted": {
            "title": "Error",
            "description": f"This player is already restricted.",
            "color": colors.red,
            "footer": "default"
        },
            "not_restricted": {
            "title": "Error",
            "description": f"This player is not restricted.",
            "color": colors.red,
            "footer": "default"
        },
        "no_perms_admin": {
            "title": "Error",
            "description": f"You must be an admin or higher to use this command.",
            "color": colors.red,
            "footer": "default"
        },
        "no_perms": {
            "title": "Error",
            "description": f"You don't have permissions to use this command.",
            "color": colors.red,
            "footer": "default"
        },
        "page_not_num": {
            "title": "Error",
            "description": f"Page must be a __whole__ number.",
            "color": colors.red,
            "footer": "default"
        },
        "discord_no_osu": {
            "title": "Critical Error",
            "description": f"Your discord is linked but there's no ID entry mtching your id in users table, report that to admins now.",
            "color": 0xFF0000,
            "footer": "default"
        },
        "command_worky": {
            "title": "Task Failed Successfully",
            "description": f"This command works lmfao aint no way",
            "color": 0x00FF00,
            "footer": "default"
        },
        "embed_FromCog": {
            "title": args["title"],
            "description": args["description"],
            "color": args["color"],
            "footer": "default"
        }
    }

    try:
        emb = embed_list[embed_name]
    except:
        raise IndexError('Embed not found')

    embed = discord.Embed(title=emb['title'], description=emb['description'], color=emb['color'])
    if emb['footer'] == "default":
        embed.set_footer(text=default_footer)

    return embed