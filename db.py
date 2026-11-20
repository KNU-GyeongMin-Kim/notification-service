import json
import sqlite3

DB_PATH = "notices.db"


def get_conn():
    """DB에 연결한다. 다른 함수들이 이 함수를 사용한다."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 결과를 컬럼 이름으로 읽기 위한 설정
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """테이블 4개를 만든다. 이미 있으면 그대로 둔다."""
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS notices (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        post_no        INTEGER NOT NULL UNIQUE,   -- 사이트 공지 번호 (중복 방지)
        title          TEXT NOT NULL,
        published_at   TEXT,
        url            TEXT,
        content        TEXT,
        board_category TEXT,                      -- 사이트가 지정한 분류
        images         TEXT,
        attachments    TEXT,
        fetched_at     TEXT,
        summary        TEXT,                      -- AI 요약
        category       TEXT,                      -- AI 분류
        apply_period   TEXT,                      -- 신청 기간
        target         TEXT,                      -- 지원 대상
        documents      TEXT,                      -- 제출 서류
        notified       INTEGER NOT NULL DEFAULT 0 -- 1: 알림 완료 또는 기존 공지
    );

    CREATE TABLE IF NOT EXISTS users (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        email     TEXT NOT NULL UNIQUE,
        notify_on INTEGER NOT NULL DEFAULT 1      -- 1: 알림 받음
    );

    CREATE TABLE IF NOT EXISTS keywords (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id),
        word    TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS sent_log (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   INTEGER NOT NULL REFERENCES users(id),
        notice_id INTEGER NOT NULL REFERENCES notices(id),
        sent_at   TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (user_id, notice_id)               -- 같은 공지를 같은 사용자에게 중복 발송 방지
    );
    """)
    conn.commit()
    conn.close()


def notice_exists(post_no):
    """해당 공지가 DB에 이미 있는지 확인한다."""
    conn = get_conn()
    row = conn.execute("SELECT 1 FROM notices WHERE post_no = ?", (post_no,)).fetchone()
    conn.close()
    return row is not None


def add_notice(notice, is_initial=False):
    """공지 1건(dict)을 저장한다. 새로 저장하면 True, 이미 있으면 False.
    is_initial=True이면 기존 공지로 보고 알림을 보내지 않는다."""
    if notice_exists(notice["post_no"]):
        return False
    conn = get_conn()
    conn.execute(
        """INSERT INTO notices
           (post_no, title, published_at, url, content, board_category,
            images, attachments, fetched_at,
            summary, category, apply_period, target, documents, notified)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            notice["post_no"], notice["title"], notice.get("date"), notice.get("url"),
            notice.get("content"), notice.get("board_category"),
            json.dumps(notice.get("images", []), ensure_ascii=False),
            json.dumps(notice.get("attachments", []), ensure_ascii=False),
            notice.get("collected_at"),
            notice.get("summary"), notice.get("category"),
            notice.get("apply_period"), notice.get("target"),
            json.dumps(notice.get("documents", []), ensure_ascii=False),
            1 if is_initial else 0,
        ),
    )
    conn.commit()
    conn.close()
    return True


def get_notice(notice_id):
    """id로 공지 1건을 가져온다."""
    conn = get_conn()
    row = conn.execute("SELECT * FROM notices WHERE id = ?", (notice_id,)).fetchone()
    conn.close()
    return row


def get_notices(limit=20):
    """최신 공지 목록을 가져온다 (화면 표시용)."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM notices ORDER BY published_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return rows


def save_summary(notice_id, summary):
    """AI가 만든 요약을 저장한다."""
    conn = get_conn()
    conn.execute("UPDATE notices SET summary = ? WHERE id = ?", (summary, notice_id))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    conn = get_conn()
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print("테이블:", [r["name"] for r in rows])
    conn.close()