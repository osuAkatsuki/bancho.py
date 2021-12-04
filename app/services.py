import databases

import config

DB_DSN = (
    "User ID={user};Password={password};Server={host};Database={db};Port={port}".format(
        **config.mysql
    )
)

database = databases.Database(DB_DSN)
