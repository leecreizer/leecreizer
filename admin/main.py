"""대시보드."""
from __future__ import annotations

from flask import Blueprint, redirect, render_template, url_for

from .auth import login_required
from .db import get_db

bp = Blueprint("main", __name__)


@bp.route("/")
def home():
    return redirect(url_for("main.dashboard"))


@bp.route("/dashboard")
@login_required
def dashboard():
    db = get_db()

    def count(sql: str) -> int:
        return db.execute(sql).fetchone()[0]

    stats = {
        "channels": count("SELECT COUNT(*) FROM channels WHERE active=1"),
        "groups": count("SELECT COUNT(*) FROM user_groups WHERE active=1"),
        "users": count("SELECT COUNT(*) FROM users WHERE active=1"),
        "categories": count("SELECT COUNT(*) FROM categories WHERE active=1"),
        "contents": count("SELECT COUNT(*) FROM contents"),
        "published": count("SELECT COUNT(*) FROM contents WHERE status='published'"),
        "no_master": count(
            "SELECT COUNT(*) FROM contents c"
            " LEFT JOIN content_master m ON m.content_id=c.id WHERE m.content_id IS NULL"
        ),
        "tags": count("SELECT COUNT(*) FROM tags WHERE active=1"),
    }
    recent = db.execute(
        "SELECT * FROM contents ORDER BY updated_at DESC, id DESC LIMIT 5"
    ).fetchall()
    return render_template("dashboard.html", stats=stats, recent=recent)
