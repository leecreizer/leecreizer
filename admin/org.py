"""유통 채널 / 사용자 그룹 / 사용자 관리."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from .auth import login_required
from .db import get_db, now

bp = Blueprint("org", __name__, url_prefix="/org")


@bp.route("/")
@login_required
def index():
    db = get_db()
    channels = db.execute(
        "SELECT c.*,"
        " (SELECT COUNT(*) FROM user_groups g WHERE g.channel_id = c.id) AS group_count"
        " FROM channels c ORDER BY c.sort_order, c.id"
    ).fetchall()
    groups = db.execute(
        "SELECT g.*, c.name AS channel_name,"
        " (SELECT COUNT(*) FROM users u WHERE u.group_id = g.id) AS user_count"
        " FROM user_groups g JOIN channels c ON c.id = g.channel_id"
        " ORDER BY c.sort_order, g.id"
    ).fetchall()
    users = db.execute(
        "SELECT u.*, g.name AS group_name, c.name AS channel_name"
        " FROM users u"
        " LEFT JOIN user_groups g ON g.id = u.group_id"
        " LEFT JOIN channels c ON c.id = g.channel_id"
        " ORDER BY u.id"
    ).fetchall()
    return render_template("org.html", channels=channels, groups=groups, users=users)


# ---------- 채널 ----------

@bp.route("/channels/save", methods=["POST"])
@login_required
def channel_save():
    db = get_db()
    cid = request.form.get("id")
    code = request.form.get("code", "").strip().upper()
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    active = 1 if request.form.get("active") else 0
    if not code or not name:
        flash("채널 코드와 이름은 필수입니다.", "error")
        return redirect(url_for("org.index"))
    try:
        if cid:
            db.execute(
                "UPDATE channels SET code=?, name=?, description=?, active=? WHERE id=?",
                (code, name, description, active, cid),
            )
            flash(f"채널 '{name}' 정보를 수정했습니다.", "success")
        else:
            db.execute(
                "INSERT INTO channels (code, name, description, active, sort_order)"
                " VALUES (?,?,?,?, (SELECT COALESCE(MAX(sort_order),0)+1 FROM channels))",
                (code, name, description, active),
            )
            flash(f"채널 '{name}'을(를) 추가했습니다.", "success")
        db.commit()
    except db.IntegrityError:
        flash(f"채널 코드 '{code}'가 이미 존재합니다.", "error")
    return redirect(url_for("org.index"))


@bp.route("/channels/<int:cid>/delete", methods=["POST"])
@login_required
def channel_delete(cid: int):
    db = get_db()
    cnt = db.execute(
        "SELECT COUNT(*) FROM user_groups WHERE channel_id=?", (cid,)
    ).fetchone()[0]
    if cnt:
        flash("소속 그룹이 있는 채널은 삭제할 수 없습니다. 그룹을 먼저 이동/삭제하세요.", "error")
    else:
        db.execute("DELETE FROM category_channels WHERE channel_id=?", (cid,))
        db.execute("DELETE FROM channels WHERE id=?", (cid,))
        db.commit()
        flash("채널을 삭제했습니다.", "success")
    return redirect(url_for("org.index"))


# ---------- 사용자 그룹 ----------

@bp.route("/groups/save", methods=["POST"])
@login_required
def group_save():
    db = get_db()
    gid = request.form.get("id")
    name = request.form.get("name", "").strip()
    channel_id = request.form.get("channel_id")
    description = request.form.get("description", "").strip()
    active = 1 if request.form.get("active") else 0
    if not name or not channel_id:
        flash("그룹 이름과 소속 채널은 필수입니다.", "error")
        return redirect(url_for("org.index"))
    if gid:
        db.execute(
            "UPDATE user_groups SET name=?, channel_id=?, description=?, active=? WHERE id=?",
            (name, channel_id, description, active, gid),
        )
        flash(f"그룹 '{name}' 정보를 수정했습니다.", "success")
    else:
        db.execute(
            "INSERT INTO user_groups (name, channel_id, description, active) VALUES (?,?,?,?)",
            (name, channel_id, description, active),
        )
        flash(f"그룹 '{name}'을(를) 추가했습니다.", "success")
    db.commit()
    return redirect(url_for("org.index"))


@bp.route("/groups/<int:gid>/delete", methods=["POST"])
@login_required
def group_delete(gid: int):
    db = get_db()
    cnt = db.execute("SELECT COUNT(*) FROM users WHERE group_id=?", (gid,)).fetchone()[0]
    if cnt:
        flash("소속 사용자가 있는 그룹은 삭제할 수 없습니다.", "error")
    else:
        db.execute("DELETE FROM user_groups WHERE id=?", (gid,))
        db.commit()
        flash("그룹을 삭제했습니다.", "success")
    return redirect(url_for("org.index"))


# ---------- 사용자 ----------

@bp.route("/users/save", methods=["POST"])
@login_required
def user_save():
    db = get_db()
    uid = request.form.get("id")
    username = request.form.get("username", "").strip()
    name = request.form.get("name", "").strip()
    role = request.form.get("role", "manager")
    group_id = request.form.get("group_id") or None
    password = request.form.get("password", "")
    active = 1 if request.form.get("active") else 0
    if not username or not name:
        flash("아이디와 이름은 필수입니다.", "error")
        return redirect(url_for("org.index"))
    try:
        if uid:
            db.execute(
                "UPDATE users SET username=?, name=?, role=?, group_id=?, active=? WHERE id=?",
                (username, name, role, group_id, active, uid),
            )
            if password:
                db.execute(
                    "UPDATE users SET password_hash=? WHERE id=?",
                    (generate_password_hash(password), uid),
                )
            flash(f"사용자 '{name}' 정보를 수정했습니다.", "success")
        else:
            if not password:
                flash("신규 사용자는 비밀번호가 필수입니다.", "error")
                return redirect(url_for("org.index"))
            db.execute(
                "INSERT INTO users (username, password_hash, name, role, group_id, active, created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (username, generate_password_hash(password), name, role, group_id, active, now()),
            )
            flash(f"사용자 '{name}'을(를) 추가했습니다.", "success")
        db.commit()
    except db.IntegrityError:
        flash(f"아이디 '{username}'가 이미 존재합니다.", "error")
    return redirect(url_for("org.index"))


@bp.route("/users/<int:uid>/delete", methods=["POST"])
@login_required
def user_delete(uid: int):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if user and user["role"] == "admin":
        admins = db.execute(
            "SELECT COUNT(*) FROM users WHERE role='admin' AND active=1"
        ).fetchone()[0]
        if admins <= 1:
            flash("마지막 관리자 계정은 삭제할 수 없습니다.", "error")
            return redirect(url_for("org.index"))
    db.execute("DELETE FROM users WHERE id=?", (uid,))
    db.commit()
    flash("사용자를 삭제했습니다.", "success")
    return redirect(url_for("org.index"))
