from copy import deepcopy

from sqlalchemy import BIGINT
from sqlalchemy import CHAR
from sqlalchemy import Column
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import FLOAT
from sqlalchemy import INT
from sqlalchemy import MetaData
from sqlalchemy import SMALLINT
from sqlalchemy import Table
from sqlalchemy import VARCHAR

metadata = MetaData()

maps_columns = (
    Column("server", Enum, primary_key=True),
    Column("id", INT, primary_key=True, unique=True),
    Column("set_id", INT),
    Column("status", INT),
    Column("md5", CHAR(32), unique=True),
    Column("artist", VARCHAR(128)),
    Column("title", VARCHAR(128)),
    Column("version", VARCHAR(128)),
    Column("creator", VARCHAR(19)),
    Column("filename", VARCHAR(256)),
    Column("last_update", DateTime),
    Column("total_length", INT),
    Column("max_combo", INT),
    Column("frozen", SMALLINT),
    Column("plays", INT),
    Column("passes", INT),
    Column("mode", SMALLINT),
    Column("bpm", FLOAT(2)),
    Column("cs", FLOAT(2)),
    Column("ar", FLOAT(2)),
    Column("od", FLOAT(2)),
    Column("hp", FLOAT(2)),
    Column("diff", FLOAT(3)),
)

scores_columns = (
    Column("id", BIGINT, primary_key=True, autoincrement=True, nullable=True),
    Column("map_md5", CHAR(32)),
    Column("score", INT),
    Column("pp", FLOAT(3)),
    Column("acc", FLOAT(3)),
    Column("max_combo", INT),
    Column("mods", INT),
    Column("n300", INT),
    Column("n100", INT),
    Column("n50", INT),
    Column("nmiss", INT),
    Column("ngeki", INT),
    Column("nkatu", INT),
    Column("grade", VARCHAR(2)),
    Column("status", SMALLINT),
    Column("mode", SMALLINT),
    Column("play_time", DateTime),
    Column("time_elapsed", INT),
    Column("client_flags", INT),
    Column("userid", INT),
    Column("perfect", SMALLINT),
    Column("online_checksum", CHAR(32)),
)

favourites_columns = (
    Column("userid", INT, primary_key=True),
    Column("setid", INT, primary_key=True),
)

users_columns = (
    Column("id", INT, autoincrement=True, primary_key=True),
    Column("name", VARCHAR(32), unique=True),
    Column("safe_name", VARCHAR(32), unique=True),
    Column("email", VARCHAR(254), unique=True),
    Column("priv", INT),
    Column("pw_bcrypt", CHAR(60)),
    Column("country", CHAR(2)),
    Column("silence_end", INT),
    Column("donor_end", INT),
    Column("creation_time", INT),
    Column("latest_acitvity", INT),
    Column("clan_id", INT),
    Column("clan_priv", SMALLINT),
    Column("api_key", CHAR(36), unique=True),
)

stats_columns = (
    Column("id", INT, autoincrement=True, primary_key=True),
    Column("mode", SMALLINT, primary_key=True),
    Column("tscore", BIGINT),
    Column("rscore", BIGINT),
    Column("pp", INT),
    Column("plays", INT),
    Column("playtime", INT),
    Column("acc", FLOAT(3)),
    Column("max_combo", INT),
    Column("xh_count", INT),
    Column("x_count", INT),
    Column("sh_count", INT),
    Column("s_count", INT),
    Column("a_count", INT),
)

ratings_columns = (
    Column("userid", INT, primary_key=True),
    Column("map_md5", CHAR(32), primary_key=True),
    Column("rating", SMALLINT),
)

clans_columns = (
    Column("id", INT, autoincrement=True, primary_key=True),
    Column("name", VARCHAR(16), unique=True),
    Column("tag", VARCHAR(6), unique=True),
    Column("owner", INT, unique=True),
    Column("created_at", DateTime),
)

comments_columns = (
    Column("id", INT, autoincrement=True, primary_key=True),
    Column("target_id", INT),
    Column("target_type", Enum("replay", "map", "song")),
    Column("userid", INT),
    Column("time", INT),
    Column("comment", VARCHAR(80)),
    Column("colour", CHAR(6)),
)

mail_columns = (
    Column("id", INT, autoincrement=True, primary_key=True),
    Column("from_id", INT),
    Column("to_id", INT),
    Column("msg", VARCHAR(2048)),
    Column("time", INT),
    Column("read", SMALLINT),
)

ingame_logins_columns = (
    Column("id", INT, autoincrement=True, primary_key=True),
    Column("userid", INT),
    Column("ip", VARCHAR(45)),
    Column("osu_ver", Date),
    Column("osu_stream", VARCHAR(11)),
    Column("datetime", DateTime),
)

client_hashes_columns = (
    Column("userid", INT, primary_key=True),
    Column("osupath", CHAR(32), primary_key=True),
    Column("adapters", CHAR(32), primary_key=True),
    Column("uninstall_id", CHAR(32), primary_key=True),
    Column("disk_serial", CHAR(32), primary_key=True),
    Column("latest_time", DateTime, primary_key=True),
    Column("occurrences", INT, primary_key=True),
)

maps = Table("maps", metadata, *maps_columns)

# XXX: deepcopy since the function takes ownership, and it cannot be used more than once
scores = Table("scores_vn", metadata, *deepcopy(scores_columns))
scores_rx = Table("scores_rx", metadata, *deepcopy(scores_columns))
scores_ap = Table("scores_ap", metadata, *deepcopy(scores_columns))

favourites = Table("favourites", metadata, *favourites_columns)

users = Table("users", metadata, *users_columns)
stats = Table("stats", metadata, *stats_columns)

ratings = Table("ratings", metadata, *ratings_columns)

clans = Table("clans", metadata, *clans_columns)

comments = Table("comments", metadata, *comments_columns)

mail = Table("mail", metadata, *mail_columns)

ingame_logins = Table("ingame_logins", metadata, *ingame_logins_columns)
client_hashes = Table("client_hashes", metadata, *client_hashes_columns)
