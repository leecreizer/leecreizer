"""설계리스트 노출용 태그 폴더/태그 마스터 관리."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .auth import login_required
from .db import get_db

bp = Blueprint("tags", __name__, url_prefix="/tags")


@bp.route("/")
@login_required
def index():
    db = get_db()
    folders = db.execute(
        "SELECT * FROM tag_folders ORDER BY sort_order, id"
    ).fetchall()
    tags_by_folder: dict[int, list] = {}
    for t in db.execute(
        "SELECT t.*,"
        " (SELECT COUNT(*) FROM content_tags ct WHERE ct.tag_id = t.id) AS usage_count"
        " FROM tags t ORDER BY t.sort_order, t.id"
    ):
        tags_by_folder.setdefault(t["folder_id"], []).append(t)
    return render_template("tags.html", folders=folders, tags_by_folder=tags_by_folder)


@bp.route("/folders/save", methods=["POST"])
@login_required
def folder_save():
    db = get_db()
    fid = request.form.get("id")
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    active = 1 if request.form.get("active") else 0
    if not name:
        flash("폴더 이름은 필수입니다.", "error")
        return redirect(url_for("tags.index"))
    try:
        if fid:
            db.execute(
                "UPDATE tag_folders SET name=?, description=?, active=? WHERE id=?",
                (name, description, active, fid),
            )
            flash(f"태그 폴더 '{name}'을(를) 수정했습니다.", "success")
        else:
            db.execute(
                "INSERT INTO tag_folders (name, description, active, sort_order)"
                " VALUES (?,?,?, (SELECT COALESCE(MAX(sort_order),0)+1 FROM tag_folders))",
                (name, description, active),
            )
            flash(f"태그 폴더 '{name}'을(를) 추가했습니다.", "success")
        db.commit()
    except db.IntegrityError:
        flash(f"폴더 이름 '{name}'이 이미 존재합니다.", "error")
    return redirect(url_for("tags.index"))


@bp.route("/folders/<int:fid>/delete", methods=["POST"])
@login_required
def folder_delete(fid: int):
    db = get_db()
    used = db.execute(
        "SELECT COUNT(*) FROM content_tags ct JOIN tags t ON t.id = ct.tag_id"
        " WHERE t.folder_id = ?",
        (fid,),
    ).fetchone()[0]
    if used:
        flash(f"콘텐츠에 매핑된 태그가 {used}건 있어 폴더를 삭제할 수 없습니다.", "error")
    else:
        db.execute("DELETE FROM tags WHERE folder_id=?", (fid,))
        db.execute("DELETE FROM tag_folders WHERE id=?", (fid,))
        db.commit()
        flash("태그 폴더를 삭제했습니다.", "success")
    return redirect(url_for("tags.index"))


@bp.route("/save", methods=["POST"])
@login_required
def tag_save():
    db = get_db()
    tid = request.form.get("id")
    folder_id = request.form.get("folder_id")
    name = request.form.get("name", "").strip()
    color = request.form.get("color", "#6b7280")
    active = 1 if request.form.get("active") else 0
    if not name or not folder_id:
        flash("태그 이름과 폴더는 필수입니다.", "error")
        return redirect(url_for("tags.index"))
    try:
        if tid:
            db.execute(
                "UPDATE tags SET folder_id=?, name=?, color=?, active=? WHERE id=?",
                (folder_id, name, color, active, tid),
            )
            flash(f"태그 '{name}'을(를) 수정했습니다.", "success")
        else:
            db.execute(
                "INSERT INTO tags (folder_id, name, color, active, sort_order)"
                " VALUES (?,?,?,?, (SELECT COALESCE(MAX(sort_order),0)+1 FROM tags WHERE folder_id=?))",
                (folder_id, name, color, active, folder_id),
            )
            flash(f"태그 '{name}'을(를) 추가했습니다.", "success")
        db.commit()
    except db.IntegrityError:
        flash(f"같은 폴더에 태그 '{name}'이 이미 존재합니다.", "error")
    return redirect(url_for("tags.index"))


@bp.route("/<int:tid>/delete", methods=["POST"])
@login_required
def tag_delete(tid: int):
    db = get_db()
    db.execute("DELETE FROM tags WHERE id=?", (tid,))
    db.commit()
    flash("태그를 삭제했습니다.", "success")
    return redirect(url_for("tags.index"))
