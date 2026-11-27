"""새 공지를 관심 키워드·분류가 맞는 사용자에게 이메일로 알린다.

흐름: 알림 대기 공지 -> 알림을 켠 사용자마다 키워드·구독 분류 대조 -> 맞으면 메일 -> 발송 기록 -> 공지 알림 완료

- 같은 사용자에게 같은 공지는 한 번만 보낸다 (발송 기록 sent_log 로 확인).
- 메일 한 통이라도 실패하면 그 공지는 알림 완료로 표시하지 않는다. 다음 차례에 실패한 사람에게만 다시 보낸다.
- 작성된 지 NOTIFY_MAX_AGE_DAYS 일이 넘은 공지는 더 시도하지 않고 알림 완료로 표시한다 (주소 오류 등으로 끝없이 재시도하지 않게).
- 메일 서버에 연결할 수 없으면 아무것도 표시하지 않고 다음 차례에 다시 시도한다.

필요한 DB 함수 (database/db.py):
    get_notices_to_notify(limit, require_summary) -> [공지 dict]
    get_subscribers() -> [{"id", "email", "name", "keywords": [..], "categories": [..]}]
    was_sent(user_id, notice_id) -> bool
    log_sent(user_id, notice_id) -> bool
    mark_notified(notice_id)
"""

import logging
import threading
from datetime import datetime, timedelta

from database import db

from . import config
from .mailer import Mailer, build_notice_email, match_keywords

log = logging.getLogger(__name__)

_lock = threading.Lock()
_missing_logged = False

REQUIRED_DB_FUNCTIONS = ("get_notices_to_notify", "get_subscribers", "was_sent", "log_sent", "mark_notified")

last_notify = {"started_at": None, "finished_at": None, "notices": 0, "sent": 0, "failed": 0, "error": None}


def match_user(notice, user):
    """사용자에게 이 공지를 보낼 이유. (맞은 키워드 목록, 맞은 분류 목록). 둘 다 비면 보내지 않는다."""
    keywords = match_keywords(notice, user.get("keywords") or [])
    category = notice.get("category")
    categories = [category] if category and category in (user.get("categories") or []) else []
    return keywords, categories


def notify_pending(limit=50):
    """알림 대기 공지를 처리한다. (처리한 공지 수, 보낸 메일 수, 실패한 메일 수)를 돌려준다."""
    if not _db_ready():
        return 0, 0, 0
    if not _lock.acquire(blocking=False):
        return 0, 0, 0
    try:
        # LLM 을 끈 상태면 요약을 기다리지 않는다 (요약 없이 원문 링크로 알림)
        notices = db.get_notices_to_notify(limit=limit, require_summary=config.LLM_ENABLED)
        if not notices:
            return 0, 0, 0
        last_notify.update(started_at=_now(), finished_at=None, notices=len(notices), sent=0, failed=0, error=None)

        subscribers = db.get_subscribers()
        sent = failed = 0
        try:
            with Mailer() as mailer:
                for notice in notices:
                    s, f = _notify_one(mailer, notice, subscribers)
                    sent += s
                    failed += f
        except Exception as e:  # 메일 서버 연결·로그인 실패: 아무것도 표시하지 않고 다음 차례에 다시
            last_notify.update(finished_at=_now(), error=f"메일 서버 연결 실패: {e}")
            log.error("메일 서버에 연결할 수 없어 알림을 다음 차례로 미룹니다: %s", e)
            return 0, sent, failed

        last_notify.update(finished_at=_now(), sent=sent, failed=failed)
        if sent or failed:
            log.info("알림: 공지 %d건, 메일 %d통 발송, %d통 실패", len(notices), sent, failed)
        return len(notices), sent, failed
    finally:
        _lock.release()


def _notify_one(mailer, notice, subscribers):
    sent = failed = 0
    for user in subscribers:
        keywords, categories = match_user(notice, user)
        if not (keywords or categories):
            continue
        if db.was_sent(user["id"], notice["id"]):
            continue
        msg = build_notice_email(notice, user["email"], keywords, categories)
        if mailer.send(msg):
            db.log_sent(user["id"], notice["id"])
            sent += 1
        else:
            failed += 1

    if failed == 0 or _too_old(notice):
        db.mark_notified(notice["id"])
        if failed:
            log.warning("[%d] 발송 실패 %d통이 있지만 오래된 공지라 더 시도하지 않습니다.", notice["post_no"], failed)
    return sent, failed


def _too_old(notice):
    try:
        posted = datetime.strptime((notice.get("published_at") or "")[:10], "%Y-%m-%d")
    except ValueError:
        return True
    return datetime.now() - posted > timedelta(days=config.NOTIFY_MAX_AGE_DAYS)


def _db_ready():
    """필요한 DB 함수가 아직 없으면 알림을 건너뛴다 (한 번만 안내)."""
    global _missing_logged
    missing = [name for name in REQUIRED_DB_FUNCTIONS if not hasattr(db, name)]
    if missing and not _missing_logged:
        log.warning("알림에 필요한 DB 함수가 아직 없어 알림을 건너뜁니다: %s", ", ".join(missing))
        _missing_logged = True
    return not missing


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
