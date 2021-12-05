from copy import deepcopy

from sqlalchemy import BigInteger
from sqlalchemy import Boolean
from sqlalchemy import CHAR
from sqlalchemy import Column
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import MetaData
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import Unicode
from sqlalchemy.sql.sqltypes import SmallInteger


metadata = MetaData()


maps = Table(
    "maps",
    metadata,
    Column(
        "server",
        Enum("osu!", "gulag"),
        server_default="osu!",
        primary_key=True,
    ),
    Column("id", Integer, primary_key=True, unique=True),
    Column("set_id", Integer),
    Column("status", Integer),
    Column("md5", CHAR(32), unique=True),
    Column("artist", Unicode(128)),
    Column("title", Unicode(128)),
    Column("version", Unicode(128)),
    Column("creator", Unicode(19)),
    Column("filename", Unicode(256)),
    Column("last_update", DateTime),
    Column("total_length", Integer),
    Column("max_combo", Integer),
    Column("frozen", Boolean),
    Column("plays", Integer),
    Column("passes", Integer),
    Column("mode", SmallInteger),
    Column("bpm", Float(2)),
    Column("cs", Float(2)),
    Column("ar", Float(2)),
    Column("od", Float(2)),
    Column("hp", Float(2)),
    Column("diff", Float(3)),
)


mapsets = Table(
    "mapsets",
    metadata,
    # TODO: enum might need name & server_default
    Column(
        "server",
        Enum("osu!", "gulag"),
        server_default="osu!",
        primary_key=True,
    ),
    Column("id", Integer, primary_key=True, unique=True),
    Column("last_osuapi_check", DateTime),
)


# NOTE: there are 3 (identical) scores tables, both vanilla, relax, and autopilot
scores_columns = (
    Column("id", BigInteger, primary_key=True, autoincrement=True, nullable=True),
    Column("map_md5", CHAR(32)),
    Column("score", Integer),
    Column("pp", Float(3)),
    Column("acc", Float(3)),
    Column("max_combo", Integer),
    Column("mods", Integer),
    Column("n300", Integer),
    Column("n100", Integer),
    Column("n50", Integer),
    Column("nmiss", Integer),
    Column("ngeki", Integer),
    Column("nkatu", Integer),
    Column("grade", String(2)),
    Column("status", SmallInteger),
    Column("mode", SmallInteger),
    Column("play_time", DateTime),
    Column("time_elapsed", Integer),
    Column("client_flags", Integer),
    Column("userid", Integer),
    Column("perfect", Boolean),
    Column("online_checksum", CHAR(32), unique=True),
)

# XXX: deepcopy since the function takes ownership, and it cannot be used more than once
scores = Table("scores_vn", metadata, *deepcopy(scores_columns))
scores_rx = Table("scores_rx", metadata, *deepcopy(scores_columns))
scores_ap = Table("scores_ap", metadata, *deepcopy(scores_columns))


favourites = Table(
    "favourites",
    metadata,
    Column("userid", Integer, primary_key=True),
    Column("setid", Integer, primary_key=True),
)


users = Table(
    "users",
    metadata,
    Column("id", Integer, autoincrement=True, primary_key=True),
    Column("name", Unicode(32), unique=True),
    Column("safe_name", Unicode(32), unique=True),
    Column("email", String(254), unique=True),
    Column("priv", Integer),
    Column("pw_bcrypt", CHAR(60)),
    Column("country", CHAR(2)),
    Column("silence_end", Integer),
    Column("donor_end", Integer),
    Column("creation_time", Integer),
    Column("latest_activity", Integer),
    Column("clan_id", Integer),
    Column("clan_priv", SmallInteger),
    Column("api_key", CHAR(36), unique=True),
)


stats = Table(
    "stats",
    metadata,
    Column("id", Integer, autoincrement=True, primary_key=True),
    Column("mode", SmallInteger, primary_key=True),
    Column("tscore", BigInteger),
    Column("rscore", BigInteger),
    Column("pp", Integer),
    Column("plays", Integer),
    Column("playtime", Integer),
    Column("acc", Float(3)),
    Column("max_combo", Integer),
    Column("xh_count", Integer),
    Column("x_count", Integer),
    Column("sh_count", Integer),
    Column("s_count", Integer),
    Column("a_count", Integer),
)


ratings = Table(
    "ratings",
    metadata,
    Column("userid", Integer, primary_key=True),
    Column("map_md5", CHAR(32), primary_key=True),
    Column("rating", SmallInteger),
)


clans = Table(
    "clans",
    metadata,
    Column("id", Integer, autoincrement=True, primary_key=True),
    Column("name", Unicode(16), unique=True),
    Column("tag", Unicode(6), unique=True),
    Column("owner", Integer, unique=True),
    Column("created_at", DateTime),
)


comments = Table(
    "comments",
    metadata,
    Column("id", Integer, autoincrement=True, primary_key=True),
    Column("target_id", Integer),
    Column("target_type", Enum("replay", "map", "song")),
    Column("userid", Integer),
    Column("time", Integer),
    Column("comment", Unicode(80)),
    Column("colour", CHAR(6)),
)


channels = Table(
    "channels",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(32), unique=True),
    Column("topic", String(256)),
    Column("read_priv", Integer),
    Column("write_priv", Integer),
    Column("auto_join", Boolean),
)


mail = Table(
    "mail",
    metadata,
    Column("id", Integer, autoincrement=True, primary_key=True),
    Column("from_id", Integer),
    Column("to_id", Integer),
    Column("msg", Unicode(2048)),
    Column("time", Integer),
    Column("read", Boolean),
)


ingame_logins = Table(
    "ingame_logins",
    metadata,
    Column("id", Integer, autoincrement=True, primary_key=True),
    Column("userid", Integer),
    Column("ip", String(45)),
    Column("osu_ver", Date),
    Column("osu_stream", String(11)),
    Column("datetime", DateTime),
)


client_hashes = Table(
    "client_hashes",
    metadata,
    Column("userid", Integer, primary_key=True),
    Column("osupath", CHAR(32), primary_key=True),
    Column("adapters", CHAR(32), primary_key=True),
    Column("uninstall_id", CHAR(32), primary_key=True),
    Column("disk_serial", CHAR(32), primary_key=True),
    Column("latest_time", DateTime, primary_key=True),
    Column("occurrences", Integer, primary_key=True),
)


tourney_pools = Table(
    "tourney_pools",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(16)),
    Column("created_at", DateTime),
    Column("created_by", Integer),
)


tourney_pool_maps = Table(
    "tourney_pool_maps",
    metadata,
    Column("map_id", Integer, primary_key=True),
    Column("pool_id", Integer, primary_key=True),
    Column("mods", Integer),
    Column("slot", SmallInteger),
)


achievements = Table(
    "achievements",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("file", String(128), unique=True),
    Column("name", Unicode(128), unique=True),
    Column("desc", Unicode(256), unique=True),
    Column("cond", String(64)),
)


logs = Table(
    "logs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("from", Integer),
    Column("to", Integer),
    Column("msg", Unicode(2048)),
    Column("time", DateTime),
)


relationships = Table(
    "relationships",
    metadata,
    Column("user1", Integer, primary_key=True),
    Column("user2", Integer, primary_key=True),
    Column("type", Enum("friend", "block")),
)


user_achievements = Table(
    "user_achievements",
    metadata,
    Column("userid", Integer, primary_key=True),
    Column("achid", Integer, primary_key=True),
)


map_requests = Table(
    "map_requests",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("map_id", Integer),
    Column("player_id", Integer),
    Column("datetime", DateTime),
    Column("active", Boolean),
)


startups = Table(
    "startups",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ver_major", SmallInteger),
    Column("ver_minor", SmallInteger),
    Column("ver_micro", SmallInteger),
    Column("datetime", DateTime),
)
