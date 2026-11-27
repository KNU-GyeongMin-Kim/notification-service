import os
import sqlite3
from datetime import datetime

from database import db

db.DB_PATH = "test_users.db"  # 테스트용 별도 DB
if os.path.exists(db.DB_PATH):
    os.remove(db.DB_PATH)

# 1) 구조 변경 장치: 예전 구조의 DB가 새 구조로 올라가는지
old = sqlite3.connect(db.DB_PATH)
old.execute("CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "email TEXT NOT NULL UNIQUE, notify_on INTEGER NOT NULL DEFAULT 1)")
old.execute("INSERT INTO users (email) VALUES ('old@example.com')")
old.commit()
old.close()
db.init_db()
db.init_db()  # 두 번 실행해도 안전해야 한다
conn = db.get_conn()
assert conn.execute("PRAGMA user_version").fetchone()[0] == len(db.MIGRATIONS)
conn.close()
old_user = db.get_user_by_email("old@example.com")
assert old_user["name"] is None and old_user["password_hash"] is None
print("구조 변경: 통과")

# 2) 회원가입, 이메일 중복
uid = db.create_user("a@example.com", "노디르벡", "hash123")
assert uid is not None
assert db.create_user("a@example.com", "다른 사람", "x") is None
user = db.get_user(uid)
assert user["name"] == "노디르벡" and user["password_hash"] == "hash123" and user["notify_on"] == 1
assert db.get_user_by_email("a@example.com")["id"] == uid
assert db.get_user(9999) is None and db.get_user_by_email("none@example.com") is None
print("회원가입/중복: 통과")

# 3) 설정 변경 (넘긴 값만)
assert db.update_user_settings(uid, name="새 이름") is True
assert db.get_user(uid)["name"] == "새 이름" and db.get_user(uid)["notify_on"] == 1
assert db.update_user_settings(uid, notify_on=False) is True
assert db.get_user(uid)["notify_on"] == 0 and db.get_user(uid)["name"] == "새 이름"
assert db.update_user_settings(uid) is False
assert db.update_user_settings(9999, name="x") is False
db.update_user_settings(uid, notify_on=True)
print("설정 변경: 통과")

# 4) 키워드 추가/중복/삭제
assert db.add_keyword(uid, "  장학금 ") is True      # 공백은 지워서 저장
assert db.add_keyword(uid, "장학금") is False         # 중복
assert db.add_keyword(uid, "   ") is False            # 빈 글자
assert db.add_keyword(uid, "인턴") is True
assert db.list_keywords(uid) == ["장학금", "인턴"]
assert db.remove_keyword(uid, "장학금") is True
assert db.remove_keyword(uid, "장학금") is False
assert db.list_keywords(uid) == ["인턴"]
print("키워드: 통과")

# 5) 분류 구독 (전체 덮어쓰기)
assert db.set_subscriptions(uid, ["학사", "장학", "학사"]) is True
assert db.list_subscriptions(uid) == ["학사", "장학"]
assert db.set_subscriptions(uid, ["취업·인턴"]) is True
assert db.list_subscriptions(uid) == ["취업·인턴"]
print("분류 구독: 통과")

# 6) 공지 3건: 대기 / 요약 완료 / 본문 없음(건너뜀)
db.add_notice({"post_no": 101, "title": "대기", "content": "본문"})
db.add_notice({"post_no": 102, "title": "완료", "content": "본문", "summary": "요약"})
db.add_notice({"post_no": 103, "title": "이미지", "content": ""})
n102 = db.get_notice_by_post_no(102)
n103 = db.get_notice_by_post_no(103)

# 7) 저장한 공지
assert db.save_notice_for_user(uid, n102["id"]) is True
assert db.save_notice_for_user(uid, n102["id"]) is False
assert db.save_notice_for_user(uid, n103["id"]) is True
assert [n["post_no"] for n in db.list_saved(uid)] == [103, 102]  # 최근 저장 순
assert db.unsave_notice(uid, n103["id"]) is True
assert db.unsave_notice(uid, n103["id"]) is False
assert [n["post_no"] for n in db.list_saved(uid)] == [102]
print("저장한 공지: 통과")

# 8) 알림 흐름
assert [n["post_no"] for n in db.get_notices_to_notify()] == [102, 103]  # 대기(101) 제외, 오래된 것부터
assert [n["post_no"] for n in db.get_notices_to_notify(require_summary=False)] == [101, 102, 103]

mine = [s for s in db.get_subscribers() if s["id"] == uid]
assert mine == [{"id": uid, "email": "a@example.com", "name": "새 이름",
                 "keywords": ["인턴"], "categories": ["취업·인턴"]}]
db.update_user_settings(uid, notify_on=False)
assert all(s["id"] != uid for s in db.get_subscribers())  # 알림 끈 사용자는 제외
db.update_user_settings(uid, notify_on=True)

assert db.was_sent(uid, n102["id"]) is False
assert db.log_sent(uid, n102["id"]) is True
assert db.was_sent(uid, n102["id"]) is True
assert db.log_sent(uid, n102["id"]) is False  # 중복 발송 방지
conn = db.get_conn()
sent_at = conn.execute("SELECT sent_at FROM sent_log").fetchone()["sent_at"]
conn.close()
now = datetime.strptime(db._now(), "%Y-%m-%d %H:%M:%S")
assert abs((now - datetime.strptime(sent_at, "%Y-%m-%d %H:%M:%S")).total_seconds()) < 60  # 한국 시간

assert db.mark_notified(n102["id"]) is True
assert [n["post_no"] for n in db.get_notices_to_notify()] == [103]
assert [n["post_no"] for n in db.get_notices_to_notify(require_summary=False)] == [101, 103]
print("알림 흐름: 통과")

# 9) 사용자를 지우면 딸린 기록이 같이 지워지는지
conn = db.get_conn()
conn.execute("DELETE FROM users WHERE id = ?", (uid,))
conn.commit()
left = sum(conn.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"]
           for t in ("keywords", "category_subscriptions", "saved_notices", "sent_log"))
conn.close()
assert left == 0
print("사용자 삭제 시 같이 지워짐: 통과")
print("전부 통과")