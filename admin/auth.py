"""로그인/로그아웃 및 인증 데코레이터."""
from __future__ import annotations

import functools

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for,
)
from werkzeug.security import check_password_hash

from .db import get_db

bp = Blueprint("auth", __name__)


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            "SELECT u.*, ug.name AS group_name, c.name AS channel_name"
            " FROM users u"
            " LEFT JOIN user_groups ug ON ug.id = u.group_id"
            " LEFT JOIN channels c ON c.id = ug.channel_id"
            " WHERE u.id = ? AND u.active = 1",
            (user_id,),
        ).fetchone()


@bp.before_app_request
def enforce_role():
    """권한 정책: org(채널·그룹·사용자)는 관리자 전용, 조회자는 읽기 전용."""
    if g.get("user") is None:
        return None
    ep = request.endpoint or ""
    if ep.startswith(("auth.", "static", "api.")):
        return None
    if ep.startswith("org.") and g.user["role"] != "admin":
        flash("채널·그룹·사용자 관리는 관리자만 접근할 수 있습니다.", "error")
        return redirect(url_for("main.dashboard"))
    if g.user["role"] == "viewer" and request.method == "POST":
        flash("조회자 권한으로는 변경할 수 없습니다. 관리자에게 권한을 요청하세요.", "error")
        ref = request.referrer or ""
        if ref.startswith(request.host_url):
            return redirect(ref)
        return redirect(url_for("main.dashboard"))
    return None


def login_required(view):
    @functools.wraps(view)
    def wrapped(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.path))
        return view(**kwargs)

    return wrapped


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM users WHERE username = ? AND active = 1", (username,)
        ).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("아이디 또는 비밀번호가 올바르지 않습니다.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            next_url = request.args.get("next") or url_for("main.dashboard")
            return redirect(next_url)
    if g.get("user"):
        return redirect(url_for("main.dashboard"))
    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    flash("로그아웃되었습니다.", "info")
    return redirect(url_for("auth.login"))
