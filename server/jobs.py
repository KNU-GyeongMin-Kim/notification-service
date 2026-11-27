"""주기적으로 도는 작업: 새 공지 수집 -> 요약(LLM) -> 알림(이메일)."""

import logging
import threading
from datetime import datetime, timedelta

from database import db
from crawler.crawl import crawl_new, crawl_since

from . import config, notifier, summarizer

log = logging.getLogger(__name__)

# 수집이 겹쳐 돌지 않게 막는 잠금 (기간 수집은 1시간 넘게 걸릴 수 있음)
_lock = threading.Lock()

# 마지막 수집 결과. /api/health 에서 보여준다.
last_crawl = {"mode": None, "started_at": None, "finished_at": None, "saved": 0, "error": None}


def crawl_job():
    """10분마다 도는 수집.

    DB가 비어 있으면 최근 FIRST_RUN_DAYS 일치를 기간 수집하고,
    아니면 마지막 글번호 이후의 새 글만 가져온다.
    """
    if db.get_last_post_no() is None:
        backfill_job(config.FIRST_RUN_DAYS)
    elif _run("new", _crawl_new):
        # 새 공지가 있으면 2분 주기를 기다리지 않고 바로 요약하고 알린다
        summarizer.summarize_pending()
        notifier.notify_pending()


def summarize_job():
    """2분마다 도는 요약과 알림. 요약 대기 공지를 SUMMARIZE_BATCH 건씩 처리하고, 요약이 끝난 새 공지를 알린다."""
    summarizer.summarize_pending()
    notifier.notify_pending()


def backfill_job(days):
    """최근 days일 안의 글을 모두 가져와 저장한다. 이미 있는 글은 건너뛴다.

    기존 공지로 저장하므로 알림을 보내지 않는다. 중간에 멈춰도 다시 실행하면 남은 글만 가져온다.
    """
    _run(f"backfill {days}d", lambda: _crawl_since(days))


def _crawl_since(days):
    saved = 0
    for notice in crawl_since(days, skip=db.notice_exists):
        if db.add_notice(notice, is_initial=True):
            saved += 1
            last_crawl["saved"] = saved  # 오래 걸리므로 진행 상황을 바로 보여준다
    return saved


def _crawl_new():
    notices = crawl_new(db.get_last_post_no())
    saved = 0
    for n in notices:
        if db.add_notice(n, is_initial=_too_old(n)):
            saved += 1
    return saved


def _too_old(notice):
    """작성된 지 NOTIFY_MAX_AGE_DAYS 일이 넘은 글은 새 글로 잡혀도 알림을 보내지 않는다.

    기간 수집이 중간에 멈춘 뒤 새 글 수집이 옛 글을 줍는 경우 등을 막는 안전장치.
    """
    try:
        posted = datetime.strptime(notice["date"][:10], "%Y-%m-%d")
    except (TypeError, ValueError):
        return False
    return datetime.now() - posted > timedelta(days=config.NOTIFY_MAX_AGE_DAYS)


def _run(mode, work):
    """수집 작업을 잠금 안에서 실행한다. 저장한 공지 수를 돌려준다 (건너뛰거나 실패하면 0)."""
    if not _lock.acquire(blocking=False):
        log.info("이전 수집이 아직 진행 중이라 이번 차례는 건너뜁니다.")
        return 0
    try:
        last_crawl.update(mode=mode, started_at=_now(), finished_at=None, saved=0, error=None)
        saved = work()
        last_crawl.update(finished_at=_now(), saved=saved)
        log.info("수집 완료(%s): 새 공지 %d건 저장", mode, saved)
        return saved
    except Exception as e:
        last_crawl.update(finished_at=_now(), error=str(e))
        log.exception("수집 실패(%s)", mode)
        return 0
    finally:
        _lock.release()


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
