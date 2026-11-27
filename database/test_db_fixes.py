import os
import sqlite3

import db

db.DB_PATH = "test_fixes.db"  # 테스트용 별도 DB
if os.path.exists(db.DB_PATH):
    os.remove(db.DB_PATH)
db.init_db()

with_text = {"post_no": 1, "title": "본문 공지", "date": "2026-11-12 09:00", "url": "https://example.com",
             "content": "본문", "board_category": "학사", "images": ["a.png"], "attachments": [],
             "collected_at": "2026-11-14 10:00"}
image_only = {"post_no": 2, "title": "이미지 공지", "content": "", "images": ["b.png"]}
waiting = {"post_no": 3, "title": "대기 공지", "content": "본문"}
for notice in (with_text, image_only, waiting):
    db.add_notice(notice)

db.save_ai_result(1, {"summary": "요약", "category": "학사", "application_period": "11/17~11/19",
                      "target": "교직 이수자", "documents": ["신청서"]})
notice = db.get_notice(1)
print("AI 결과:", notice["application_period"], notice["summary_status"])
print("요약 대기:", [n["post_no"] for n in db.get_notices_to_summarize()])
print("이미지 공지:", db.get_notice(2)["summary_status"])
print("images 타입:", type(notice["images"]).__name__, notice["images"])

conn = db.get_conn()
conn.execute("INSERT INTO users (email) VALUES ('a@example.com')")
user_id = conn.execute("SELECT id FROM users").fetchone()["id"]
conn.execute("INSERT INTO keywords (user_id, word) VALUES (?, '장학금')", (user_id,))
conn.execute("INSERT INTO sent_log (user_id, notice_id) VALUES (?, 1)", (user_id,))
conn.commit()

try:
    conn.execute("INSERT INTO keywords (user_id, word) VALUES (?, '장학금')", (user_id,))
    print("키워드 중복: 막지 못함 (문제)")
except sqlite3.IntegrityError:
    print("키워드 중복: 막힘")

conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
conn.commit()
left = (conn.execute("SELECT COUNT(*) AS c FROM keywords").fetchone()["c"]
        + conn.execute("SELECT COUNT(*) AS c FROM sent_log").fetchone()["c"])
print("삭제 후 남은 키워드/발송 기록:", left)
conn.close()