import databases

import app.settings

database = databases.Database(app.settings.DB_DSN)
