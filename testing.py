from typing import Tuple, Any
from packets import PacketReader, Packet, write
from constants.types import osuTypes
from constants.privileges import Privileges, BanchoPrivileges

def testUserStats(data: bytes) -> Tuple[Any]:
    pr = PacketReader(data)
    return pr.read(
        osuTypes.i32, # userid
        osuTypes.i8, # action
        osuTypes.string, # infotext
        osuTypes.string, # beatmap md5
        osuTypes.i32, # mods
        osuTypes.i8, # gamemode
        osuTypes.i32, # beatmap_id
        osuTypes.i64, # rscore
        osuTypes.f32, # acc
        osuTypes.i32, # playcount
        osuTypes.i64, # tscore
        osuTypes.i32, # rank
        osuTypes.i16 # pp
    )

def testUserPresence(data: bytes) -> Tuple[Any]:
    pr = PacketReader(data)
    return pr.read(
        (osuTypes.i32), # userid
        (osuTypes.string), # name
        (osuTypes.i8), # utc offset
        (osuTypes.i8), # country
        (osuTypes.i8), # bancho priv
        (osuTypes.f32), # lat
        (osuTypes.f32), # long
        (osuTypes.i32) # rank
    )

tests = (
    {
        'name': 'userStats',
        'call': testUserStats,
        #'data': b'\x0b\x00\x00.\x00\x00\x00\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x039\x01\x0e\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00@@\x0c\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xfb\x1d',
        'data': write(
            Packet.s_userStats,
            (3, osuTypes.i32), # id
            (0, osuTypes.i8), # action
            ('', osuTypes.string), # infotext
            ('', osuTypes.string), # beatmap md5
            (0, osuTypes.i32), # mods
            (3, osuTypes.i8), # gamemode
            (917817, osuTypes.i32), # beatmap id
            (2147483648, osuTypes.i64), # rscore
            (0, osuTypes.f32), # acc
            (5, osuTypes.i32), # playcount
            (6, osuTypes.i64), # tscore
            (6, osuTypes.i32), # rank
            (6, osuTypes.i16)), # pp
        'running': True
    }, {
        'name': 'userPresence',
        'call': testUserPresence,
        'data': write(
            Packet.s_userPresence,
            (1001, osuTypes.i32),
            ('cmyui', osuTypes.string),
            (24 + -4, osuTypes.i8),
            (38, osuTypes.i8), # break break
            (BanchoPrivileges.Player | BanchoPrivileges.Supporter, osuTypes.i8),
            (79.32, osuTypes.f32), # lat
            (43.59, osuTypes.f32), # long
            (5, osuTypes.i32)),
        'running': True
    }
)

if __name__ == '__main__':
    from struct import unpack
    print('Running tests.')
    for t in (t for t in tests if t['running']):
        _id, _len = unpack('<HxI', t['data'][:7])
        print(f"{t['name']} (ID: {_id} | L: {_len}): {t['call'](t['data'][7:])}")
