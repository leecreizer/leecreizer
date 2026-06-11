"""설계 페이지 연동용 공개 API (읽기 전용).

설계 페이지(프론트)는 이 API로 채널별 노출 카테고리 트리와
노출(published) 콘텐츠 리스트를 조회한다. 어드민에서 노출로 설정한
데이터만 내려가므로 별도 인증 없이 읽기 전용으로 제공한다.
"""
from __future__ import annotations

import sqlite3

from flask import Blueprint, jsonify, request

from .categories import descendant_ids
from .db import get_db

bp = Blueprint("api", __name__, url_prefix="/api")


def find_channel(db: sqlite3.Connection, code: str):
    return db.execute(
        "SELECT id, code, name FROM channels WHERE code=? AND active=1",
        (code.upper(),),
    ).fetchone()


def exposed_category_ids(db: sqlite3.Connection, channel_id: int) -> set[int]:
    """채널에 노출되는 카테고리 집합. 상위가 미노출/비활성이면 하위도 제외."""
    rows = {
        r["id"]: r
        for r in db.execute("SELECT id, parent_id, active FROM categories")
    }
    raw = {
        r["category_id"]
        for r in db.execute(
            "SELECT category_id FROM category_channels WHERE channel_id=?",
            (channel_id,),
        )
    }
    ok: set[int] = set()
    for cid in raw:
        cur: int | None = cid
        good = True
        while cur is not None:
            row = rows.get(cur)
            if row is None or not row["active"] or cur not in raw:
                good = False
                break
            cur = row["parent_id"]
        if good:
            ok.add(cid)
    return ok


@bp.route("/channels/<code>/categories")
def channel_categories(code: str):
    """채널별 설계 페이지 노출 카테고리 트리."""
    db = get_db()
    channel = find_channel(db, code)
    if channel is None:
        return jsonify({"error": f"channel '{code}' not found"}), 404
    ok = exposed_category_ids(db, channel["id"])

    rows = db.execute(
        "SELECT id, parent_id, name, sort_order FROM categories"
        " WHERE active=1 ORDER BY sort_order, id"
    ).fetchall()
    nodes = {
        r["id"]: {"id": r["id"], "name": r["name"], "children": []}
        for r in rows if r["id"] in ok
    }
    tree: list[dict] = []
    for r in rows:
        if r["id"] not in ok:
            continue
        parent = nodes.get(r["parent_id"])
        if parent:
            parent["children"].append(nodes[r["id"]])
        else:
            tree.append(nodes[r["id"]])
    return jsonify({
        "channel": {"code": channel["code"], "name": channel["name"]},
        "categories": tree,
    })


@bp.route("/channels/<code>/contents")
def channel_contents(code: str):
    """채널별 노출(published) 콘텐츠 리스트 + 마스터 + 태그.

    쿼리 파라미터:
      category_id  해당 카테고리(하위 포함)로 한정
      tag          태그 이름. 여러 번 지정 시 모두 보유한 콘텐츠만 (AND)
      q            콘텐츠명/코드 검색
    """
    db = get_db()
    channel = find_channel(db, code)
    if channel is None:
        return jsonify({"error": f"channel '{code}' not found"}), 404
    ok = exposed_category_ids(db, channel["id"])

    target_ids = ok
    category_id = request.args.get("category_id", type=int)
    if category_id:
        target_ids = ok & set(descendant_ids(db, category_id))
    if not target_ids:
        return jsonify({"channel": dict(channel), "count": 0, "items": []})

    placeholders = ",".join("?" * len(target_ids))
    sql = (
        "SELECT ct.*, cm.brand, cm.model_no, cm.price, cm.unit,"
        " cm.width_mm, cm.depth_mm, cm.height_mm, cm.material, cm.color,"
        " cm.manufacturer, cm.origin, cm.release_date"
        " FROM contents ct LEFT JOIN content_master cm ON cm.content_id = ct.id"
        f" WHERE ct.status = 'published' AND ct.category_id IN ({placeholders})"
    )
    params: list = list(target_ids)
    q = request.args.get("q", "").strip()
    if q:
        sql += " AND (ct.name LIKE ? OR ct.code LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    sql += " ORDER BY ct.sort_order, ct.updated_at DESC"
    rows = db.execute(sql, params).fetchall()

    tag_map: dict[int, list[dict]] = {}
    for r in db.execute(
        "SELECT ct.content_id, t.name, t.color, f.name AS folder"
        " FROM content_tags ct"
        " JOIN tags t ON t.id = ct.tag_id AND t.active = 1"
        " JOIN tag_folders f ON f.id = t.folder_id"
        " ORDER BY f.sort_order, t.sort_order"
    ):
        tag_map.setdefault(r["content_id"], []).append(
            {"folder": r["folder"], "name": r["name"], "color": r["color"]}
        )

    want_tags = [t.strip() for t in request.args.getlist("tag") if t.strip()]
    items = []
    for r in rows:
        tags = tag_map.get(r["id"], [])
        tag_names = {t["name"] for t in tags}
        if want_tags and not all(t in tag_names for t in want_tags):
            continue
        items.append({
            "code": r["code"],
            "name": r["name"],
            "category_id": r["category_id"],
            "thumbnail_url": r["thumbnail_url"],
            "description": r["description"],
            "master": {
                "brand": r["brand"], "model_no": r["model_no"],
                "price": r["price"], "unit": r["unit"],
                "width_mm": r["width_mm"], "depth_mm": r["depth_mm"],
                "height_mm": r["height_mm"], "material": r["material"],
                "color": r["color"], "manufacturer": r["manufacturer"],
                "origin": r["origin"], "release_date": r["release_date"],
            },
            "tags": tags,
        })
    return jsonify({
        "channel": {"code": channel["code"], "name": channel["name"]},
        "count": len(items),
        "items": items,
    })
