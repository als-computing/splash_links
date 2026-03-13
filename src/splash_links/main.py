"""Entry point: uvicorn splash_links.main:app"""

import os

from .app import create_app

app = create_app(db_path=os.environ.get("SPLASH_LINKS_DB", "links.duckdb"))
