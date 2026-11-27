import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
# DB 파일 위치: 프로그램을 어느 폴더에서 실행해도 db.py가 있는 폴더에 만든다.
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notices.db")

SUMMARY_STATUSES = ("pending", "done", "failed", "skipped")
JSON_COLUMNS = ("images", "attachments", "documents")

KST = timezone(timedelta(hours=9))  # 한국 시간


def _now():
    """현재 한국 시간을 'YYYY-MM-DD HH:MM:SS' 문자열로 돌려준다."""
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")


# DB 구조 변경 목록. 번호는 PRAGMA user_version에 기록되고, 아직 적용 안 된 것만 실행된다.
# 이미 적용된 항목은 수정하지 말고, 새 변경은 맨 아래에 추가한다.
MIGRATIONS = [
    # 1: users 로그인 칸 (비밀번호 해시는 서버가 만들어서 넘긴다)
    """ALTER TABLE users ADD COLUMN name TEXT;
       ALTER TABLE users ADD COLUMN password_hash TEXT;
       ALTER TABLE users ADD COLUMN created_at TEXT;""",
    # 2: 저장한 공지, 분류 구독
    """CREATE TABLE saved_notices (
           id        INTEGER PRIMARY KEY AUTOINCREMENT,
           user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
           notice_id INTEGER NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
           saved_at  TEXT,
           UNIQUE (user_id, notice_id)
       );
       CREATE TABLE category_subscriptions (
           id       INTEGER PRIMARY KEY AUTOINCREMENT,
           user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
           category TEXT NOT NULL,
           UNIQUE (user_id, category)
       );""",
]


def _run_migrations(conn):
    """아직 적용 안 된 변경만 차례로 실행한다. 변경 하나는 통째로 성공하거나 통째로 취소된다."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for number, sql in enumerate(MIGRATIONS, start=1):
        if number <= current:
            continue
        conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")

def get_conn():
    """DB에 연결한다. 다른 함수들이 이 함수를 사용한다."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 결과를 컬럼 이름으로 읽기 위한 설정
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """기본 테이블을 만들고, 구조 변경(MIGRATIONS)을 적용한다. 몇 번을 실행해도 안전하다."""
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
    _run_migrations(conn)
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
    """저장된 실제 공지 중 가장 큰 게시판 글번호. 없으면 None. (시연용 공지는 음수 번호라 제외)"""
    conn = get_conn()
    row = conn.execute("SELECT MAX(post_no) FROM notices WHERE post_no > 0").fetchone()
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


def get_notices_to_summarize_new_first(limit=20):
    """요약 대기 공지를 알림 대상(notified=0)부터, 그 안에서는 최신 글부터 가져온다.

    기간 수집으로 쌓인 옛 공지 수백 건 뒤에서 새 공지가 기다리지 않게 하기 위해서다.
    """
    conn = get_conn()
    rows = conn.execute(
        """SELECT * FROM notices WHERE summary_status = 'pending'
           ORDER BY notified ASC, post_no DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [_to_dict(row) for row in rows]


def count_summary_status():
    """요약 상태별 공지 개수. {"pending": 3, "done": 10, ...}"""
    conn = get_conn()
    rows = conn.execute("SELECT summary_status, COUNT(*) FROM notices GROUP BY summary_status").fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


# 시연용 공지: 실제 게시판 글과 겹치지 않게 음수 글번호(-1, -2, ...)를 쓴다.


def next_demo_post_no():
    """다음 시연용 공지 글번호 (-1, -2, ...)."""
    conn = get_conn()
    row = conn.execute("SELECT MIN(post_no) FROM notices WHERE post_no < 0").fetchone()
    conn.close()
    return (row[0] or 0) - 1


def list_demo_notices():
    """시연용 공지 목록 (최근 것부터)."""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM notices WHERE post_no < 0 ORDER BY post_no").fetchall()
    conn.close()
    return [_to_dict(row) for row in rows]


def delete_demo_notices():
    """시연용 공지와 그 발송 기록을 모두 지운다. 지운 공지 수를 돌려준다. 실제 공지는 건드리지 않는다."""
    conn = get_conn()
    conn.execute("DELETE FROM sent_log WHERE notice_id IN (SELECT id FROM notices WHERE post_no < 0)")
    deleted = conn.execute("DELETE FROM notices WHERE post_no < 0").rowcount
    conn.commit()
    conn.close()
    return deleted


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

# ---------------------------------------------------------------- 사용자·알림 (노디르벡)


def create_user(email, name, password_hash):
    """새 사용자를 만들고 id를 돌려준다. 이메일이 이미 있으면 None.
    비밀번호 해시는 서버가 만들어서 넘기고, DB는 저장만 한다."""
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO users (email, name, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (email, name, password_hash, _now()),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_user_by_email(email):
    """이메일로 사용자 1명을 dict로 가져온다. 없으면 None. (로그인 확인용으로 password_hash 포함)"""
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user(user_id):
    """id로 사용자 1명을 dict로 가져온다. 없으면 None. (password_hash 포함)"""
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_user_settings(user_id, notify_on=None, name=None):
    """넘긴 값만 바꾼다. 바뀌었으면 True, 사용자가 없거나 바꿀 값이 없으면 False."""
    fields, params = [], []
    if notify_on is not None:
        fields.append("notify_on = ?")
        params.append(1 if notify_on else 0)
    if name is not None:
        fields.append("name = ?")
        params.append(name)
    if not fields:
        return False
    conn = get_conn()
    cur = conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", params + [user_id])
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


# ---- 키워드

def add_keyword(user_id, word):
    """키워드를 추가하면 True, 이미 있거나 빈 글자면 False. 앞뒤 공백은 지워서 저장한다."""
    word = (word or "").strip()
    if not word:
        return False
    conn = get_conn()
    try:
        conn.execute("INSERT INTO keywords (user_id, word) VALUES (?, ?)", (user_id, word))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def remove_keyword(user_id, word):
    """키워드를 지운다. 지웠으면 True, 없었으면 False."""
    conn = get_conn()
    cur = conn.execute(
        "DELETE FROM keywords WHERE user_id = ? AND word = ?", (user_id, (word or "").strip())
    )
    conn.commit()
    removed = cur.rowcount > 0
    conn.close()
    return removed


def list_keywords(user_id):
    """사용자의 키워드 글자 목록. 예: ["장학금", "인턴"]"""
    conn = get_conn()
    rows = conn.execute("SELECT word FROM keywords WHERE user_id = ? ORDER BY id", (user_id,)).fetchall()
    conn.close()
    return [r["word"] for r in rows]


# ---- 분류 구독

def set_subscriptions(user_id, categories):
    """분류 구독 목록 전체를 새로 덮어쓴다. 성공하면 True, 사용자가 없으면 False."""
    cleaned = []
    for category in categories:
        category = (category or "").strip()
        if category and category not in cleaned:
            cleaned.append(category)
    conn = get_conn()
    try:
        conn.execute("DELETE FROM category_subscriptions WHERE user_id = ?", (user_id,))
        conn.executemany(
            "INSERT INTO category_subscriptions (user_id, category) VALUES (?, ?)",
            [(user_id, c) for c in cleaned],
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        conn.rollback()
        return False
    finally:
        conn.close()


def list_subscriptions(user_id):
    """사용자가 구독한 분류 글자 목록. 예: ["학사", "장학"]"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT category FROM category_subscriptions WHERE user_id = ? ORDER BY id", (user_id,)
    ).fetchall()
    conn.close()
    return [r["category"] for r in rows]


# ---- 저장한 공지

def save_notice_for_user(user_id, notice_id):
    """공지를 저장하면 True, 이미 저장했거나 사용자·공지가 없으면 False."""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO saved_notices (user_id, notice_id, saved_at) VALUES (?, ?, ?)",
            (user_id, notice_id, _now()),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def unsave_notice(user_id, notice_id):
    """저장한 공지를 해제한다. 해제했으면 True, 저장돼 있지 않았으면 False."""
    conn = get_conn()
    cur = conn.execute(
        "DELETE FROM saved_notices WHERE user_id = ? AND notice_id = ?", (user_id, notice_id)
    )
    conn.commit()
    removed = cur.rowcount > 0
    conn.close()
    return removed


def list_saved(user_id):
    """사용자가 저장한 공지 dict 목록. 최근 저장 순."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT n.* FROM saved_notices s JOIN notices n ON n.id = s.notice_id
           WHERE s.user_id = ? ORDER BY s.saved_at DESC, s.id DESC""",
        (user_id,),
    ).fetchall()
    conn.close()
    return [_to_dict(row) for row in rows]


# ---- 알림 흐름

def get_notices_to_notify(limit=50, require_summary=True):
    """알림 처리가 안 된(notified = 0) 공지를 오래된 것부터 돌려준다.
    require_summary=True(기본): 요약이 끝난(done, failed, skipped) 공지만.
    require_summary=False: 요약 상태와 상관없이 notified = 0인 공지 (LLM을 끈 상태에서도 알림 가능)."""
    sql = "SELECT * FROM notices WHERE notified = 0"
    if require_summary:
        sql += " AND summary_status IN ('done', 'failed', 'skipped')"
    sql += " ORDER BY post_no ASC LIMIT ?"
    conn = get_conn()
    rows = conn.execute(sql, (limit,)).fetchall()
    conn.close()
    return [_to_dict(row) for row in rows]


def get_subscribers():
    """알림을 받는 사용자(notify_on = 1) 목록. 키워드와 구독 분류를 같이 담는다.
    [{"id": 1, "email": "...", "name": "...", "keywords": [...], "categories": [...]}, ...]"""
    conn = get_conn()
    users = conn.execute("SELECT id, email, name FROM users WHERE notify_on = 1 ORDER BY id").fetchall()
    keywords, categories = {}, {}
    for row in conn.execute("SELECT user_id, word FROM keywords ORDER BY id"):
        keywords.setdefault(row["user_id"], []).append(row["word"])
    for row in conn.execute("SELECT user_id, category FROM category_subscriptions ORDER BY id"):
        categories.setdefault(row["user_id"], []).append(row["category"])
    conn.close()
    return [
        {
            "id": u["id"], "email": u["email"], "name": u["name"],
            "keywords": keywords.get(u["id"], []),
            "categories": categories.get(u["id"], []),
        }
        for u in users
    ]


def log_sent(user_id, notice_id):
    """발송 기록을 남기면 True, 이미 있으면 False. (중복 발송 방지) 시간은 한국 시간."""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO sent_log (user_id, notice_id, sent_at) VALUES (?, ?, ?)",
            (user_id, notice_id, _now()),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()
def was_sent(user_id, notice_id):
    """이미 보낸 기록이 있으면 True. (실패한 사람에게만 다시 보낼 때 쓴다)"""
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM sent_log WHERE user_id = ? AND notice_id = ?", (user_id, notice_id)
    ).fetchone()
    conn.close()
    return row is not None

def mark_notified(notice_id):
    """공지를 알림 처리 완료(notified = 1)로 바꾼다. 바뀌었으면 True."""
    conn = get_conn()
    cur = conn.execute("UPDATE notices SET notified = 1 WHERE id = ?", (notice_id,))
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed
if __name__ == "__main__":
    init_db()
    conn = get_conn()
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print("테이블:", [r["name"] for r in rows])
    conn.close()