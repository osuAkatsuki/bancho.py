# -*- coding: utf-8 -*-

__all__ = ()

import bcrypt
import hashlib
import os
import time
import datetime
import app.state.services

from quart import Blueprint
from quart import redirect
from quart import render_template
from quart import request
from quart import session
from quart import send_file

from app.objects.player import Player
from zenith.objects.constants import tables, mode_gulag_rev, mode2str

api = Blueprint('api', __name__)
MODE_CONVERT = {
    0: "osu!Standard",
    1: "osu!Taiko",
    2: "osu!Catch",
    3: "osu!Mania",
    4: "osu!Standard with Relax",
    5: "osu!Taiko with Relax",
    6: "osu!Catch with Relax",
    7: "osu!Standard with AutoPilot",
}
@api.route('/')
async def main():
    return {'success': False, 'msg': 'Please specify route'}

@api.route('/get_records')
async def get_records():
    #TODO: Make it faster
    records = {}
    for i in range(0, 8):
        record = await app.state.services.database.fetch_one(
            f'SELECT {tables[i]}.id, {tables[i]}.pp, {tables[i]}.userid, '
            f'maps.set_id, users.name FROM {tables[i]} LEFT JOIN users ON '
            f'{tables[i]}.userid = users.id LEFT JOIN maps ON {tables[i]}.map_md5 = '
            f'maps.md5 WHERE {tables[i]}.mode = {mode_gulag_rev[i]} && maps.status=2 '
             '&& users.priv & 1 ORDER BY pp DESC LIMIT 1;'
        )
        record = dict(record)
        record['id'] = str(record['id'])
        record['mode_str'] = MODE_CONVERT[i]
        records[mode2str[i]] = record

    return {"success": True, "records": records}

@api.route('/remove_relationship')
async def remove_relationship():
    r_type = request.args.get('type', default=None, type=str)
    target = request.args.get('target', default=None, type=str)

    # Check if logged in
    if 'authenticated' not in session:
        return {"code":403, "status":"You must be authenticated to use this route."}

    # Checks for type
    if r_type == None:
        return {"code":400, "status":"Must specify type"}
    elif r_type.lower() not in ["friend", "block"]:
        return {"code":400, "status":"Wrong type, allowed: friend, block."}

    # Checks for id
    if target == None:
        return {"code":400, "status":"Must specify target"}
    elif not target.isdigit():
        return {"code":400, "status":"Id must be a digit"}

    # Check if user has specified relationship with target user
    check1 = await glob.db.fetch(
        'SELECT * FROM relationships WHERE user1=%s AND user2=%s and type=%s',
        (session['user_data']['id'], target, r_type)
    )
    if not check1 and r_type.lower() == "friend":
        return {"code":400, "status":f"UID 4 is not friends with UID {target}"}
    if not check1 and r_type.lower() == "block":
        return {"code":400, "status":f"UID 4 is not blocking UID {target}"}
    if not check1:
        return {"code":400, "status":f"Unknown error occurred"}

    await glob.db.execute('DELETE FROM relationships WHERE user1=%s AND user2=%s AND type=%s',
                         (session['user_data']['id'], target, r_type))

    return {"success": True, "msg": f"Successfully deleted {target} from {r_type} list"}