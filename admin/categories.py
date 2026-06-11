"""설계 페이지 노출 연동 카테고리 관리 (계층 구조)."""
from __future__ import annotations

import sqlite3

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .auth import login_required
from .db import get_db

bp = Blueprint("categories", __name__, url_prefix="/categories")


def build_tree(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute(
        "SELECT c.*,"
        " (SELECT COUNT(*) FROM contents ct WHERE ct.category_id = c.id) AS content_count"
        " FROM categories c ORDER BY c.sort_order, c.id"
    ).fetchall()
    exposures: dict[int, set[int]] = {}
    for row in db.execute("SELECT category_id, channel_id FROM category_channels"):
        exposures.setdefault(row["category_id"], set()).add(row["channel_id"])

    nodes = {
        r["id"]: {**dict(r), "children": [], "channel_ids": exposures.get(r["id"], set())}
        for r in rows
    }
    roots: list[dict] = []
    for node in nodes.values():
        parent = nodes.get(node["parent_id"])
        if parent:
            parent["children"].append(node)
        else:
            roots.append(node)
    return roots


def flatten_tree(roots: list[dict], depth: int = 0) -> list[dict]:
    """셀렉트 박스용: 깊이 정보를 포함한 평탄화 리스트."""
    out: list[dict] = []
    for node in roots:
        out.append({**node, "depth": depth})
        out.extend(flatten_tree(node["children"], depth + 1))
    return out


def descendant_ids(db: sqlite3.Connection, cat_id: int) -> list[int]:
    ids = [cat_id]
    frontier = [cat_id]
    while frontier:
        placeholders = ",".join("?" * len(frontier))
        rows = db.execute(
            f"SELECT id FROM categories WHERE parent_id IN ({placeholders})", frontier
        ).fetchall()
        frontier = [r["id"] for r in rows]
        ids.extend(frontier)
    return ids


def category_path(db: sqlite3.Connection, cat_id: int | None) -> str:
    parts: list[str] = []
    while cat_id:
        row = db.execute("SELECT parent_id, name FROM categories WHERE id=?", (cat_id,)).fetchone()
        if row is None:
            break
        parts.append(row["name"])
        cat_id = row["parent_id"]
    return " > ".join(reversed(parts))


@bp.route("/")
@login_required
def index():
    db = get_db()
    tree = build_tree(db)
    channels = db.execute(
        "SELECT * FROM channels WHERE active=1 ORDER BY sort_order, id"
    ).fetchall()
    return render_template(
        "categories.html", tree=tree, flat=flatten_tree(tree), channels=channels
    )


@bp.route("/save", methods=["POST"])
@login_required
def save():
    db = get_db()
    cid = request.form.get("id")
    name = request.form.get("name", "").strip()
    parent_id = request.form.get("parent_id") or None
    active = 1 if request.form.get("active") else 0
    channel_ids = request.form.getlist("channel_ids")
    if not name:
        flash("카테고리 이름은 필수입니다.", "error")
        return redirect(url_for("categories.index"))

    if cid:
        if parent_id and int(parent_id) in descendant_ids(db, int(cid)):
            flash("자기 자신 또는 하위 카테고리로는 이동할 수 없습니다.", "error")
            return redirect(url_for("categories.index"))
        db.execute(
            "UPDATE categories SET name=?, parent_id=?, active=? WHERE id=?",
            (name, parent_id, active, cid),
        )
        db.execute("DELETE FROM category_channels WHERE category_id=?", (cid,))
        flash(f"카테고리 '{name}'을(를) 수정했습니다.", "success")
    else:
        cur = db.execute(
            "INSERT INTO categories (name, parent_id, active, sort_order)"
            " VALUES (?,?,?, (SELECT COALESCE(MAX(sort_order),0)+1 FROM categories))",
            (name, parent_id, active),
        )
        cid = cur.lastrowid
        flash(f"카테고리 '{name}'을(를) 추가했습니다.", "success")
    for ch in channel_ids:
        db.execute(
            "INSERT OR IGNORE INTO category_channels (category_id, channel_id) VALUES (?,?)",
            (cid, ch),
        )
    db.commit()
    return redirect(url_for("categories.index"))


@bp.route("/<int:cid>/delete", methods=["POST"])
@login_required
def delete(cid: int):
    db = get_db()
    ids = descendant_ids(db, cid)
    placeholders = ",".join("?" * len(ids))
    cnt = db.execute(
        f"SELECT COUNT(*) FROM contents WHERE category_id IN ({placeholders})", ids
    ).fetchone()[0]
    if cnt:
        flash(f"이 카테고리(하위 포함)에 콘텐츠 {cnt}건이 있어 삭제할 수 없습니다.", "error")
        return redirect(url_for("categories.index"))
    db.execute(f"DELETE FROM category_channels WHERE category_id IN ({placeholders})", ids)
    db.execute(f"DELETE FROM categories WHERE id IN ({placeholders})", ids)
    db.commit()
    flash("카테고리를 삭제했습니다(하위 포함).", "success")
    return redirect(url_for("categories.index"))


@bp.route("/<int:cid>/move/<direction>", methods=["POST"])
@login_required
def move(cid: int, direction: str):
    """같은 부모 안에서 정렬 순서를 위/아래로 이동."""
    db = get_db()
    me = db.execute("SELECT * FROM categories WHERE id=?", (cid,)).fetchone()
    if me is None:
        return redirect(url_for("categories.index"))
    op, order = ("<", "DESC") if direction == "up" else (">", "ASC")
    parent_cond = "parent_id IS NULL" if me["parent_id"] is None else "parent_id = ?"
    params: list = [me["sort_order"]]
    if me["parent_id"] is not None:
        params.append(me["parent_id"])
    neighbor = db.execute(
        f"SELECT * FROM categories WHERE sort_order {op} ? AND {parent_cond}"
        f" ORDER BY sort_order {order} LIMIT 1",
        params,
    ).fetchone()
    if neighbor:
        db.execute("UPDATE categories SET sort_order=? WHERE id=?", (neighbor["sort_order"], cid))
        db.execute("UPDATE categories SET sort_order=? WHERE id=?", (me["sort_order"], neighbor["id"]))
        db.commit()
    return redirect(url_for("categories.index"))
