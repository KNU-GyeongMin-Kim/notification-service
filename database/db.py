import json
import os
import sqlite3

# DB 파일 위치: 프로그램을 어느 폴더에서 실행해도 db.py가 있는 폴더에 만든다.
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notices.db")

SUMMARY_STATUSES = ("pending", "done", "failed", "skipped")
JSON_COLUMNS = ("images", "attachments", "documents")


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
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        post_no            INTEGER NOT NULL UNIQUE,   -- 사이트 공지 번호 (중복 방지)
        title              TEXT NOT NULL,
        published_at       TEXT,
        url                TEXT,
        content            TEXT,
        board_category     TEXT,                      -- 사이트가 지정한 분류
        images             TEXT,                      -- JSON 문자열
        attachments        TEXT,                      -- JSON 문자열
        fetched_at         TEXT,
        summary            TEXT,                      -- AI 요약
        summary_status     TEXT NOT NULL DEFAULT 'pending'
                           CHECK (summary_status IN ('pending', 'done', 'failed', 'skipped')),
        category           TEXT,                      -- AI 분류
        application_period TEXT,                      -- 신청 기간 (LLM 키 이름과 동일)
        target             TEXT,                      -- 지원 대상
        documents          TEXT,                      -- 제출 서류 (JSON 문자열)
        notified           INTEGER NOT NULL DEFAULT 0 -- 1: 알림 완료 또는 기존 공지
    );

    CREATE TABLE IF NOT EXISTS users (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        email     TEXT NOT NULL UNIQUE,
        notify_on INTEGER NOT NULL DEFAULT 1          -- 1: 알림 받음
    );

    CREATE TABLE IF NOT EXISTS keywords (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        word    TEXT NOT NULL,
        UNIQUE (user_id, word)                        -- 같은 키워드 중복 등록 방지
    );

    CREATE TABLE IF NOT EXISTS sent_log (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        notice_id INTEGER NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
        sent_at   TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (user_id, notice_id)                   -- 같은 공지를 같은 사용자에게 중복 발송 방지
    );
    """)
    conn.commit()
    conn.close()


def _to_dict(row):
    """sqlite3.Row를 dict로 바꾸고, JSON 문자열 컬럼은 리스트로 되돌린다."""
    if row is None:
        return None
    data = dict(row)
    for column in JSON_COLUMNS:
        data[column] = json.loads(data[column]) if data.get(column) else []
    return data


def notice_exists(post_no):
    """해당 공지가 DB에 이미 있는지 확인한다."""
    conn = get_conn()
    row = conn.execute("SELECT 1 FROM notices WHERE post_no = ?", (post_no,)).fetchone()
    conn.close()
    return row is not None


def add_notice(notice, is_initial=False):
    """공지 1건(dict)을 저장한다. 새로 저장하면 True, 이미 있으면 False.
    is_initial=True이면 기존 공지로 보고 알림을 보내지 않는다.
    키 이름은 두 가지를 모두 받는다 (date/published_at, collected_at/fetched_at,
    apply_period/application_period)."""
    if notice_exists(notice["post_no"]):
        return False

    content = notice.get("content") or ""
    if notice.get("summary"):
        status = "done"
    elif not content.strip():
        status = "skipped"   # 본문이 없는 공지(이미지만): LLM 요약을 하지 않는다
    else:
        status = "pending"

    conn = get_conn()
    conn.execute(
        """INSERT INTO notices
           (post_no, title, published_at, url, content, board_category,
            images, attachments, fetched_at,
            summary, summary_status, category, application_period, target,
            documents, notified)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            notice["post_no"], notice["title"],
            notice.get("published_at") or notice.get("date"),
            notice.get("url"), content, notice.get("board_category"),
            json.dumps(notice.get("images", []), ensure_ascii=False),
            json.dumps(notice.get("attachments", []), ensure_ascii=False),
            notice.get("fetched_at") or notice.get("collected_at"),
            notice.get("summary"), status, notice.get("category"),
            notice.get("application_period") or notice.get("apply_period"),
            notice.get("target"),
            json.dumps(notice.get("documents", []), ensure_ascii=False),
            1 if is_initial else 0,
        ),
    )
    conn.commit()
    conn.close()
    return True


def get_notice(notice_id):
    """id로 공지 1건을 dict로 가져온다. 없으면 None."""
    conn = get_conn()
    row = conn.execute("SELECT * FROM notices WHERE id = ?", (notice_id,)).fetchone()
    conn.close()
    return _to_dict(row)


def get_notices(limit=20):
    """최신 공지 목록을 dict 리스트로 가져온다 (화면 표시용)."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM notices ORDER BY published_at DESC, id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [_to_dict(row) for row in rows]


def get_notices_to_summarize(limit=20):
    """요약이 필요한(대기 상태) 공지만 가져온다."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM notices WHERE summary_status = 'pending' ORDER BY id LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [_to_dict(row) for row in rows]


def set_summary_status(notice_id, status):
    """요약 상태를 바꾼다: pending(대기), done(완료), failed(실패), skipped(건너뜀)."""
    if status not in SUMMARY_STATUSES:
        raise ValueError(f"status must be one of {SUMMARY_STATUSES}")
    conn = get_conn()
    conn.execute("UPDATE notices SET summary_status = ? WHERE id = ?", (status, notice_id))
    conn.commit()
    conn.close()


def save_summary(notice_id, summary):
    """AI가 만든 요약만 저장하고 상태를 done으로 바꾼다."""
    conn = get_conn()
    conn.execute(
        "UPDATE notices SET summary = ?, summary_status = 'done' WHERE id = ?",
        (summary, notice_id),
    )
    conn.commit()
    conn.close()


def save_ai_result(notice_id, result):
    """AI(LLM) 결과(dict)를 한 번에 저장하고 상태를 done으로 바꾼다.
    result 키: summary, category, application_period, target, documents"""
    conn = get_conn()
    conn.execute(
        """UPDATE notices
           SET summary = ?, category = ?, application_period = ?, target = ?,
               documents = ?, summary_status = 'done'
           WHERE id = ?""",
        (
            result.get("summary"), result.get("category"),
            result.get("application_period"), result.get("target"),
            json.dumps(result.get("documents", []), ensure_ascii=False),
            notice_id,
        ),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------- 서버에서 쓰려고 추가 (김문수)


def get_last_post_no():
    """저장된 공지 중 가장 큰 게시판 글번호. 공지가 하나도 없으면 None."""
    conn = get_conn()
    row = conn.execute("SELECT MAX(post_no) FROM notices").fetchone()
    conn.close()
    return row[0]


def get_notice_by_post_no(post_no):
    """게시판 글번호로 공지 1건을 dict로 가져온다. 없으면 None."""
    conn = get_conn()
    row = conn.execute("SELECT * FROM notices WHERE post_no = ?", (post_no,)).fetchone()
    conn.close()
    return _to_dict(row)


def list_notices(category=None, board_category=None, limit=20, offset=0):
    """공지 목록(dict 리스트)과 전체 개수를 돌려준다. 최신순.

    category(세부 분류, AI)와 board_category(사이트 분류)로 거를 수 있다. 둘 다 주면 둘 다 맞는 것만.
    """
    conditions, params = [], []
    if category:
        conditions.append("category = ?")
        params.append(category)
    if board_category:
        conditions.append("board_category = ?")
        params.append(board_category)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    conn = get_conn()
    total = conn.execute(f"SELECT COUNT(*) FROM notices {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM notices {where} ORDER BY published_at DESC, post_no DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    conn.close()
    return [_to_dict(row) for row in rows], total


def count_by_category(column="category"):
    """분류별 공지 개수. [(분류, 개수), ...] 많은 순. 분류가 비어 있는 공지는 뺀다.

    column: "category"(세부 분류, AI) 또는 "board_category"(사이트 분류)
    """
    if column not in ("category", "board_category"):
        raise ValueError("column must be 'category' or 'board_category'")
    conn = get_conn()
    rows = conn.execute(
        f"""SELECT {column} AS name, COUNT(*) AS cnt FROM notices
            WHERE {column} IS NOT NULL AND {column} != ''
            GROUP BY {column} ORDER BY cnt DESC"""
    ).fetchall()
    conn.close()
    return [(r["name"], r["cnt"]) for r in rows]


if __name__ == "__main__":
    init_db()
    conn = get_conn()
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print("테이블:", [r["name"] for r in rows])
    conn.close()