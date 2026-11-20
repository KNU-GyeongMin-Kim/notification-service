"""주기적으로 도는 작업: 새 공지 수집.

2주차에 요약(LLM)과 알림 발송을 이 흐름 뒤에 붙인다.
"""

import logging
import threading
from datetime import datetime

import db
from crawler.crawl import crawl_new

log = logging.getLogger(__name__)

# 수집이 겹쳐 돌지 않게 막는 잠금 (수집 한 번에 몇 분 걸릴 수 있음)
_lock = threading.Lock()

# 마지막 수집 결과. /api/health 에서 보여준다.
last_crawl = {"started_at": None, "finished_at": None, "saved": 0, "error": None}


def crawl_job():
    """새 공지를 가져와 DB에 저장한다.

    DB가 비어 있으면 첫 실행으로 보고, 저장만 하고 알림 대상에서 뺀다(is_initial).
    """
    if not _lock.acquire(blocking=False):
        log.info("이전 수집이 아직 진행 중이라 이번 차례는 건너뜁니다.")
        return
    try:
        last_crawl.update(started_at=_now(), finished_at=None, error=None)
        last_post_no = db.get_last_post_no()
        is_initial = last_post_no is None

        notices = crawl_new(last_post_no)
        saved = sum(1 for n in notices if db.add_notice(n, is_initial=is_initial))

        last_crawl.update(finished_at=_now(), saved=saved)
        log.info("수집 완료: 새 공지 %d건 저장%s", saved, " (첫 실행, 알림 없음)" if is_initial else "")

        # TODO(2주차): 새로 저장한 공지 요약(LLM) -> 키워드 맞는 사용자에게 이메일 발송
    except Exception as e:
        last_crawl.update(finished_at=_now(), error=str(e))
        log.exception("수집 실패")
    finally:
        _lock.release()


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
