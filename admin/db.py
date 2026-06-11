"""어드민 관리 시스템 SQLite 데이터베이스 레이어.

스키마 생성, 시드 데이터, 커넥션 헬퍼를 담당한다.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from flask import g
from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).resolve().parent / "admin.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS channels (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    description TEXT DEFAULT '',
    sort_order  INTEGER DEFAULT 0,
    active      INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS user_groups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id  INTEGER NOT NULL REFERENCES channels(id),
    name        TEXT NOT NULL,
    description TEXT DEFAULT '',
    active      INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name          TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'manager',  -- admin | manager | viewer
    group_id      INTEGER REFERENCES user_groups(id),
    active        INTEGER DEFAULT 1,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id  INTEGER REFERENCES categories(id),
    name       TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0,
    active     INTEGER DEFAULT 1
);

-- 카테고리의 설계 페이지 노출 여부를 유통 채널별로 제어
CREATE TABLE IF NOT EXISTS category_channels (
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    channel_id  INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    PRIMARY KEY (category_id, channel_id)
);

CREATE TABLE IF NOT EXISTS contents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id   INTEGER REFERENCES categories(id),
    code          TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'draft',  -- draft | published | hidden
    thumbnail_url TEXT DEFAULT '',
    description   TEXT DEFAULT '',
    sort_order    INTEGER DEFAULT 0,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS content_master (
    content_id   INTEGER PRIMARY KEY REFERENCES contents(id) ON DELETE CASCADE,
    brand        TEXT DEFAULT '',
    model_no     TEXT DEFAULT '',
    price        INTEGER DEFAULT 0,
    cost         INTEGER DEFAULT 0,
    unit         TEXT DEFAULT 'EA',
    width_mm     INTEGER DEFAULT 0,
    depth_mm     INTEGER DEFAULT 0,
    height_mm    INTEGER DEFAULT 0,
    material     TEXT DEFAULT '',
    color        TEXT DEFAULT '',
    manufacturer TEXT DEFAULT '',
    origin       TEXT DEFAULT '',
    release_date TEXT DEFAULT '',
    memo         TEXT DEFAULT '',
    updated_at   TEXT NOT NULL
);

-- 설계리스트 노출용 태그를 폴더(그룹) 단위로 관리
CREATE TABLE IF NOT EXISTS tag_folders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    sort_order  INTEGER DEFAULT 0,
    active      INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS tags (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_id  INTEGER NOT NULL REFERENCES tag_folders(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    color      TEXT DEFAULT '#6b7280',
    sort_order INTEGER DEFAULT 0,
    active     INTEGER DEFAULT 1,
    UNIQUE (folder_id, name)
);

CREATE TABLE IF NOT EXISTS content_tags (
    content_id INTEGER NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    tag_id     INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (content_id, tag_id)
);
"""


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        from flask import current_app

        g.db = connect(current_app.config["DB_PATH"])
    return g.db


def close_db(_exc=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(db_path: Path | str = DB_PATH) -> None:
    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            seed(conn)
    finally:
        conn.close()


def seed(conn: sqlite3.Connection) -> None:
    """최초 구동 시 기본 관리자 계정과 예시 데이터를 넣는다."""
    ts = now()

    channels = [
        ("DIRECT", "자사몰", "자사 직영 온라인몰", 1),
        ("PARTNER", "제휴몰", "외부 제휴 판매 채널", 2),
        ("AGENCY", "대리점", "오프라인 대리점/전시장", 3),
    ]
    conn.executemany(
        "INSERT INTO channels (code, name, description, sort_order) VALUES (?,?,?,?)",
        channels,
    )

    groups = [
        (1, "자사몰 운영팀", "자사몰 설계 콘텐츠 운영"),
        (2, "제휴몰 운영팀", "제휴몰 노출 콘텐츠 운영"),
        (3, "대리점 설계팀", "대리점 설계 상담 인력"),
    ]
    conn.executemany(
        "INSERT INTO user_groups (channel_id, name, description) VALUES (?,?,?)",
        groups,
    )

    conn.execute(
        "INSERT INTO users (username, password_hash, name, role, group_id, created_at)"
        " VALUES (?,?,?,?,?,?)",
        ("admin", generate_password_hash("admin1234"), "최고관리자", "admin", 1, ts),
    )

    # 계층형 카테고리: (name, parent_index|None)
    cats = [
        ("가구", None),       # 1
        ("침실", 1),          # 2
        ("침대", 2),          # 3
        ("옷장/수납장", 2),   # 4
        ("거실", 1),          # 5
        ("소파", 5),          # 6
        ("주방", None),       # 7
        ("싱크대", 7),        # 8
        ("아일랜드장", 7),    # 9
    ]
    for i, (name, parent) in enumerate(cats, start=1):
        conn.execute(
            "INSERT INTO categories (parent_id, name, sort_order) VALUES (?,?,?)",
            (parent, name, i),
        )
    # 기본으로 모든 카테고리를 모든 채널에 노출
    for cat_id in range(1, len(cats) + 1):
        for ch_id in range(1, len(channels) + 1):
            conn.execute(
                "INSERT INTO category_channels (category_id, channel_id) VALUES (?,?)",
                (cat_id, ch_id),
            )

    folders = [("스타일", "디자인 스타일 분류", 1), ("평형대", "추천 평형 분류", 2), ("가격대", "가격 구간 분류", 3)]
    conn.executemany(
        "INSERT INTO tag_folders (name, description, sort_order) VALUES (?,?,?)",
        folders,
    )
    tags = [
        (1, "모던", "#3b82f6", 1), (1, "내추럴", "#22c55e", 2), (1, "클래식", "#a16207", 3),
        (2, "20평대", "#8b5cf6", 1), (2, "30평대", "#ec4899", 2),
        (3, "보급형", "#6b7280", 1), (3, "프리미엄", "#f59e0b", 2),
    ]
    conn.executemany(
        "INSERT INTO tags (folder_id, name, color, sort_order) VALUES (?,?,?,?)",
        tags,
    )

    samples = [
        (3, "BED-001", "수면공감 평상형 침대 Q", "published"),
        (6, "SOFA-001", "모듈 패브릭 소파 3인", "published"),
        (8, "SINK-001", "유로 화이트 싱크대 2400", "draft"),
    ]
    for cat_id, code, name, status in samples:
        cur = conn.execute(
            "INSERT INTO contents (category_id, code, name, status, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?)",
            (cat_id, code, name, status, ts, ts),
        )
        conn.execute(
            "INSERT INTO content_master (content_id, brand, price, updated_at) VALUES (?,?,?,?)",
            (cur.lastrowid, "리브홈", 0, ts),
        )
    conn.execute("INSERT INTO content_tags (content_id, tag_id) VALUES (1, 1)")
    conn.execute("INSERT INTO content_tags (content_id, tag_id) VALUES (2, 2)")
    conn.commit()
