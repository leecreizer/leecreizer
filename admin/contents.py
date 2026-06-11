"""카테고리별 콘텐츠 + 마스터 정보 + 일괄등록(CSV) 관리."""
from __future__ import annotations

import csv
import io

from flask import (
    Blueprint, Response, flash, redirect, render_template, request, url_for,
)

from .auth import login_required
from .categories import build_tree, category_path, descendant_ids, flatten_tree
from .db import get_db, now

bp = Blueprint("contents", __name__, url_prefix="/contents")


def back(default_endpoint: str = "contents.index"):
    """워크스페이스 등 호출한 화면으로 복귀 (next 폼 필드, 내부 경로만 허용)."""
    nxt = request.form.get("next", "")
    if nxt.startswith("/") and not nxt.startswith("//"):
        return redirect(nxt)
    return redirect(url_for(default_endpoint))

STATUS_LABELS = {"draft": "작성중", "published": "노출", "hidden": "숨김"}
STATUS_BY_LABEL = {v: k for k, v in STATUS_LABELS.items()}

BULK_COLUMNS = [
    "콘텐츠코드", "콘텐츠명", "카테고리경로", "상태", "브랜드", "모델번호",
    "판매가", "원가", "단위", "가로(mm)", "세로(mm)", "높이(mm)",
    "재질", "색상", "제조사", "원산지", "태그",
]


# ---------- 리스트 ----------

def filtered_items(db, category_id: int | None, status: str, q: str) -> list[dict]:
    """필터 적용된 콘텐츠 + 마스터 + 태그. 리스트 화면과 CSV 내보내기가 공유."""
    sql = (
        "SELECT ct.*, (cm.content_id IS NOT NULL) AS has_master,"
        " cm.brand, cm.model_no, cm.price, cm.cost, cm.unit,"
        " cm.width_mm, cm.depth_mm, cm.height_mm, cm.material,"
        " cm.color AS master_color, cm.manufacturer, cm.origin"
        " FROM contents ct LEFT JOIN content_master cm ON cm.content_id = ct.id"
        " WHERE 1=1"
    )
    params: list = []
    if category_id:
        ids = descendant_ids(db, category_id)
        sql += f" AND ct.category_id IN ({','.join('?' * len(ids))})"
        params.extend(ids)
    if status:
        sql += " AND ct.status = ?"
        params.append(status)
    if q:
        sql += " AND (ct.name LIKE ? OR ct.code LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    sql += " ORDER BY ct.updated_at DESC, ct.id DESC"
    rows = db.execute(sql, params).fetchall()

    tag_map: dict[int, list] = {}
    for r in db.execute(
        "SELECT ct.content_id, t.name, t.color, f.name AS folder"
        " FROM content_tags ct"
        " JOIN tags t ON t.id = ct.tag_id"
        " JOIN tag_folders f ON f.id = t.folder_id"
        " ORDER BY f.sort_order, t.sort_order"
    ):
        tag_map.setdefault(r["content_id"], []).append(r)

    return [
        {
            **dict(r),
            "path": category_path(db, r["category_id"]),
            "tags": tag_map.get(r["id"], []),
        }
        for r in rows
    ]


@bp.route("/")
@login_required
def index():
    db = get_db()
    category_id = request.args.get("category_id", type=int)
    status = request.args.get("status", "")
    q = request.args.get("q", "").strip()
    items = filtered_items(db, category_id, status, q)
    flat = flatten_tree(build_tree(db))
    channels = db.execute(
        "SELECT * FROM channels WHERE active=1 ORDER BY sort_order, id"
    ).fetchall()

    # 상세 패널: ?selected=<id> 는 마스터 수정, ?new=1 은 신규 등록을 같은 화면에서 처리
    selected_id = request.args.get("selected", type=int)
    creating = request.args.get("new") is not None
    sel_content = sel_master = None
    sel_tags: set[int] = set()
    if selected_id:
        sel_content = db.execute(
            "SELECT * FROM contents WHERE id=?", (selected_id,)
        ).fetchone()
        if sel_content is None:
            selected_id = None
        else:
            sel_master = db.execute(
                "SELECT * FROM content_master WHERE content_id=?", (selected_id,)
            ).fetchone()
            sel_tags = {
                r["tag_id"]
                for r in db.execute(
                    "SELECT tag_id FROM content_tags WHERE content_id=?", (selected_id,)
                )
            }

    folders = db.execute(
        "SELECT * FROM tag_folders WHERE active=1 ORDER BY sort_order, id"
    ).fetchall()
    tags_by_folder: dict[int, list] = {}
    for t in db.execute("SELECT * FROM tags WHERE active=1 ORDER BY sort_order, id"):
        tags_by_folder.setdefault(t["folder_id"], []).append(t)

    list_args = {
        "category_id": category_id or None,
        "status": status or None,
        "q": q or None,
    }
    detail_next = url_for(
        "contents.index", **list_args, selected=selected_id if sel_content else None
    )
    return render_template(
        "contents.html",
        items=items, flat=flat, channels=channels, status_labels=STATUS_LABELS,
        f_category=category_id, f_status=status, f_q=q,
        content=sel_content, master=sel_master, selected_tags=sel_tags,
        detail_open=bool(sel_content or creating),
        preselect_category=sel_content["category_id"] if sel_content else category_id,
        folders=folders, tags_by_folder=tags_by_folder,
        list_args=list_args, detail_next=detail_next,
    )


@bp.route("/<int:cid>/quick", methods=["POST"])
@login_required
def quick_update(cid: int):
    """리스트 행에서 이름·노출상태를 바로 수정."""
    db = get_db()
    name = request.form.get("name", "").strip()
    status = request.form.get("status", "draft")
    if status not in STATUS_LABELS:
        status = "draft"
    if not name:
        flash("콘텐츠명은 비울 수 없습니다.", "error")
        return back()
    db.execute(
        "UPDATE contents SET name=?, status=?, updated_at=? WHERE id=?",
        (name, status, now(), cid),
    )
    db.commit()
    flash(f"'{name}' — {STATUS_LABELS[status]} 상태로 저장했습니다.", "success")
    return back()


# ---------- 등록/수정 (기본정보 + 마스터 + 태그 통합 폼) ----------

@bp.route("/new", methods=["GET", "POST"])
@bp.route("/<int:cid>/edit", methods=["GET", "POST"])
@login_required
def form(cid: int | None = None):
    db = get_db()
    content = master = None
    selected_tags: set[int] = set()
    if cid:
        content = db.execute("SELECT * FROM contents WHERE id=?", (cid,)).fetchone()
        if content is None:
            flash("콘텐츠를 찾을 수 없습니다.", "error")
            return redirect(url_for("contents.index"))
        master = db.execute(
            "SELECT * FROM content_master WHERE content_id=?", (cid,)
        ).fetchone()
        selected_tags = {
            r["tag_id"]
            for r in db.execute("SELECT tag_id FROM content_tags WHERE content_id=?", (cid,))
        }

    if request.method == "POST":
        f = request.form
        code = f.get("code", "").strip()
        name = f.get("name", "").strip()
        if not code or not name:
            flash("콘텐츠 코드와 이름은 필수입니다.", "error")
        else:
            dup = db.execute(
                "SELECT id FROM contents WHERE code=? AND id IS NOT ?", (code, cid)
            ).fetchone()
            if dup:
                flash(f"콘텐츠 코드 '{code}'가 이미 존재합니다.", "error")
            else:
                ts = now()
                base = (
                    f.get("category_id") or None, code, name,
                    f.get("status", "draft"), f.get("thumbnail_url", "").strip(),
                    f.get("description", "").strip(), ts,
                )
                if cid:
                    db.execute(
                        "UPDATE contents SET category_id=?, code=?, name=?, status=?,"
                        " thumbnail_url=?, description=?, updated_at=? WHERE id=?",
                        (*base, cid),
                    )
                else:
                    cur = db.execute(
                        "INSERT INTO contents (category_id, code, name, status,"
                        " thumbnail_url, description, updated_at, created_at)"
                        " VALUES (?,?,?,?,?,?,?,?)",
                        (*base, ts),
                    )
                    cid = cur.lastrowid

                def num(key: str) -> int:
                    try:
                        return int(float(f.get(key, "0") or 0))
                    except ValueError:
                        return 0

                db.execute(
                    "INSERT INTO content_master (content_id, brand, model_no, price, cost,"
                    " unit, width_mm, depth_mm, height_mm, material, color, manufacturer,"
                    " origin, release_date, memo, updated_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                    " ON CONFLICT(content_id) DO UPDATE SET brand=excluded.brand,"
                    " model_no=excluded.model_no, price=excluded.price, cost=excluded.cost,"
                    " unit=excluded.unit, width_mm=excluded.width_mm, depth_mm=excluded.depth_mm,"
                    " height_mm=excluded.height_mm, material=excluded.material,"
                    " color=excluded.color, manufacturer=excluded.manufacturer,"
                    " origin=excluded.origin, release_date=excluded.release_date,"
                    " memo=excluded.memo, updated_at=excluded.updated_at",
                    (
                        cid, f.get("brand", "").strip(), f.get("model_no", "").strip(),
                        num("price"), num("cost"), f.get("unit", "EA").strip(),
                        num("width_mm"), num("depth_mm"), num("height_mm"),
                        f.get("material", "").strip(), f.get("color", "").strip(),
                        f.get("manufacturer", "").strip(), f.get("origin", "").strip(),
                        f.get("release_date", "").strip(), f.get("memo", "").strip(), ts,
                    ),
                )
                db.execute("DELETE FROM content_tags WHERE content_id=?", (cid,))
                for tag_id in f.getlist("tag_ids"):
                    db.execute(
                        "INSERT OR IGNORE INTO content_tags (content_id, tag_id) VALUES (?,?)",
                        (cid, tag_id),
                    )
                db.commit()
                flash(f"콘텐츠 '{name}'을(를) 저장했습니다.", "success")
                return back()

    # 통합 화면에서 폴더를 선택한 채 "+ 콘텐츠"를 누르면 해당 카테고리를 미리 선택
    preselect_category = request.args.get("category_id", type=int)
    if content is not None:
        preselect_category = content["category_id"]

    flat = flatten_tree(build_tree(db))
    folders = db.execute(
        "SELECT * FROM tag_folders WHERE active=1 ORDER BY sort_order, id"
    ).fetchall()
    tags_by_folder: dict[int, list] = {}
    for t in db.execute("SELECT * FROM tags WHERE active=1 ORDER BY sort_order, id"):
        tags_by_folder.setdefault(t["folder_id"], []).append(t)
    return render_template(
        "content_form.html",
        content=content, master=master, flat=flat,
        folders=folders, tags_by_folder=tags_by_folder,
        selected_tags=selected_tags, status_labels=STATUS_LABELS,
        preselect_category=preselect_category,
    )


@bp.route("/<int:cid>/delete", methods=["POST"])
@login_required
def delete(cid: int):
    db = get_db()
    db.execute("DELETE FROM contents WHERE id=?", (cid,))
    db.commit()
    flash("콘텐츠를 삭제했습니다.", "success")
    return back()


# ---------- 내보내기 (CSV) ----------

@bp.route("/export")
@login_required
def export():
    """현재 필터 기준 콘텐츠를 일괄등록 템플릿과 같은 형식의 CSV로 다운로드.

    내려받아 수정한 뒤 그대로 일괄등록에 올리면 왕복(roundtrip) 수정이 된다.
    """
    db = get_db()
    items = filtered_items(
        db,
        request.args.get("category_id", type=int),
        request.args.get("status", ""),
        request.args.get("q", "").strip(),
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(BULK_COLUMNS)
    for it in items:
        tags = ", ".join(f"{t['folder']}>{t['name']}" for t in it["tags"])
        writer.writerow([
            it["code"], it["name"], it["path"], STATUS_LABELS[it["status"]],
            it["brand"] or "", it["model_no"] or "",
            it["price"] or 0, it["cost"] or 0, it["unit"] or "EA",
            it["width_mm"] or 0, it["depth_mm"] or 0, it["height_mm"] or 0,
            it["material"] or "", it["master_color"] or "",
            it["manufacturer"] or "", it["origin"] or "", tags,
        ])
    return Response(
        "﻿" + buf.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=contents_export.csv"},
    )


# ---------- 일괄등록 (CSV) ----------

@bp.route("/bulk", methods=["GET", "POST"])
@login_required
def bulk():
    db = get_db()
    report = None
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename:
            flash("업로드할 CSV 파일을 선택하세요.", "error")
        else:
            raw = file.read()
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("cp949", errors="replace")
            report = import_csv(db, text)
            db.commit()
    return render_template("bulk.html", report=report, columns=BULK_COLUMNS)


@bp.route("/bulk/template")
@login_required
def bulk_template():
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(BULK_COLUMNS)
    writer.writerow([
        "BED-100", "샘플 침대 프레임 SS", "가구 > 침실 > 침대", "노출", "리브홈",
        "LH-BD-100", "390000", "210000", "EA", "1200", "2050", "350",
        "PB+LPM", "화이트", "리브홈산업", "대한민국", "스타일>모던, 평형대>20평대",
    ])
    data = "﻿" + buf.getvalue()  # 엑셀 호환용 BOM
    return Response(
        data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=content_bulk_template.csv"},
    )


def resolve_category(db, path: str) -> int | None:
    """'가구 > 침실 > 침대' 형태의 경로를 카테고리 id로 변환. 없으면 생성."""
    parts = [p.strip() for p in path.split(">") if p.strip()]
    if not parts:
        return None
    parent_id = None
    for part in parts:
        cond = "parent_id IS NULL" if parent_id is None else "parent_id = ?"
        params = [part] if parent_id is None else [part, parent_id]
        row = db.execute(
            f"SELECT id FROM categories WHERE name=? AND {cond}", params
        ).fetchone()
        if row:
            parent_id = row["id"]
        else:
            cur = db.execute(
                "INSERT INTO categories (name, parent_id, sort_order)"
                " VALUES (?,?, (SELECT COALESCE(MAX(sort_order),0)+1 FROM categories))",
                (part, parent_id),
            )
            parent_id = cur.lastrowid
            # 신규 카테고리는 활성 채널 전체에 노출로 시작
            for ch in db.execute("SELECT id FROM channels WHERE active=1"):
                db.execute(
                    "INSERT OR IGNORE INTO category_channels (category_id, channel_id) VALUES (?,?)",
                    (parent_id, ch["id"]),
                )
    return parent_id


def resolve_tag(db, token: str) -> int | None:
    """'폴더>태그' 또는 '태그' 토큰을 tag id로 변환. 없으면 생성."""
    token = token.strip()
    if not token:
        return None
    if ">" in token:
        folder_name, tag_name = (s.strip() for s in token.split(">", 1))
    else:
        folder_name, tag_name = "미분류", token
    folder = db.execute("SELECT id FROM tag_folders WHERE name=?", (folder_name,)).fetchone()
    if folder:
        folder_id = folder["id"]
    else:
        folder_id = db.execute(
            "INSERT INTO tag_folders (name, sort_order)"
            " VALUES (?, (SELECT COALESCE(MAX(sort_order),0)+1 FROM tag_folders))",
            (folder_name,),
        ).lastrowid
    tag = db.execute(
        "SELECT id FROM tags WHERE folder_id=? AND name=?", (folder_id, tag_name)
    ).fetchone()
    if tag:
        return tag["id"]
    return db.execute(
        "INSERT INTO tags (folder_id, name, sort_order)"
        " VALUES (?,?, (SELECT COALESCE(MAX(sort_order),0)+1 FROM tags WHERE folder_id=?))",
        (folder_id, tag_name, folder_id),
    ).lastrowid


def import_csv(db, text: str) -> dict:
    """콘텐츠코드 기준 upsert. 행별 결과 리포트를 반환한다."""
    reader = csv.DictReader(io.StringIO(text))
    created = updated = 0
    errors: list[str] = []
    ts = now()

    def num(row: dict, key: str) -> int:
        val = (row.get(key) or "").replace(",", "").strip()
        try:
            return int(float(val)) if val else 0
        except ValueError:
            return 0

    for lineno, row in enumerate(reader, start=2):
        code = (row.get("콘텐츠코드") or "").strip()
        name = (row.get("콘텐츠명") or "").strip()
        if not code or not name:
            errors.append(f"{lineno}행: 콘텐츠코드/콘텐츠명 누락")
            continue
        category_id = resolve_category(db, row.get("카테고리경로") or "")
        status = STATUS_BY_LABEL.get((row.get("상태") or "").strip(), "draft")

        existing = db.execute("SELECT id FROM contents WHERE code=?", (code,)).fetchone()
        if existing:
            cid = existing["id"]
            db.execute(
                "UPDATE contents SET name=?, category_id=?, status=?, updated_at=? WHERE id=?",
                (name, category_id, status, ts, cid),
            )
            updated += 1
        else:
            cid = db.execute(
                "INSERT INTO contents (code, name, category_id, status, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?)",
                (code, name, category_id, status, ts, ts),
            ).lastrowid
            created += 1

        db.execute(
            "INSERT INTO content_master (content_id, brand, model_no, price, cost, unit,"
            " width_mm, depth_mm, height_mm, material, color, manufacturer, origin, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(content_id) DO UPDATE SET brand=excluded.brand,"
            " model_no=excluded.model_no, price=excluded.price, cost=excluded.cost,"
            " unit=excluded.unit, width_mm=excluded.width_mm, depth_mm=excluded.depth_mm,"
            " height_mm=excluded.height_mm, material=excluded.material, color=excluded.color,"
            " manufacturer=excluded.manufacturer, origin=excluded.origin,"
            " updated_at=excluded.updated_at",
            (
                cid, (row.get("브랜드") or "").strip(), (row.get("모델번호") or "").strip(),
                num(row, "판매가"), num(row, "원가"), (row.get("단위") or "EA").strip(),
                num(row, "가로(mm)"), num(row, "세로(mm)"), num(row, "높이(mm)"),
                (row.get("재질") or "").strip(), (row.get("색상") or "").strip(),
                (row.get("제조사") or "").strip(), (row.get("원산지") or "").strip(), ts,
            ),
        )
        tags_field = row.get("태그") or ""
        if tags_field.strip():
            db.execute("DELETE FROM content_tags WHERE content_id=?", (cid,))
            for token in tags_field.split(","):
                tag_id = resolve_tag(db, token)
                if tag_id:
                    db.execute(
                        "INSERT OR IGNORE INTO content_tags (content_id, tag_id) VALUES (?,?)",
                        (cid, tag_id),
                    )
    return {"created": created, "updated": updated, "errors": errors}
