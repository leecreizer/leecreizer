"""쿠홈 스타일 설계프로그램 어드민 관리 시스템 (Flask 앱 팩토리)."""
from __future__ import annotations

import os
from pathlib import Path

from flask import Flask

from . import db as db_module
from .db import close_db, init_db


def create_app(db_path: str | os.PathLike | None = None) -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("ADMIN_SECRET_KEY", "dev-secret-change-me")
    app.config["DB_PATH"] = Path(db_path) if db_path else db_module.DB_PATH

    init_db(app.config["DB_PATH"])
    app.teardown_appcontext(close_db)

    from . import api, auth, categories, contents, main, org, tags

    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(org.bp)
    app.register_blueprint(categories.bp)
    app.register_blueprint(contents.bp)
    app.register_blueprint(tags.bp)
    app.register_blueprint(api.bp)
    return app
