"""요약 대기 공지를 LLM(Ollama)으로 요약·분류해 DB에 저장한다.

LLM 쪽 함수(llm/ollama_test.py 의 summarize_and_classify)를 그대로 부른다.
서버는 순서와 실패 처리만 맡는다.

- Ollama 에 연결할 수 없으면(꺼짐, 주소 틀림, 모델 없음) 이번 차례를 멈추고 공지는 대기 상태로 둔다.
  Ollama 가 다시 켜지면 다음 차례에 이어서 처리한다.
- 모델 응답이 형식에 맞지 않으면 그 공지만 실패(failed)로 표시하고 다음 공지로 넘어간다.
"""

import json
import logging
import socket
import threading
import time
from urllib.error import HTTPError, URLError

from database import db

from . import config

log = logging.getLogger(__name__)

_lock = threading.Lock()
_ollama_ok = None  # 마지막 연결 상태. 상태가 바뀔 때만 로그를 남겨 같은 경고가 반복되지 않게 한다.

last_summary = {"started_at": None, "finished_at": None, "done": 0, "failed": 0, "pending_left": None, "error": None}


class LLMUnavailable(Exception):
    """Ollama 에 연결할 수 없음. 공지 탓이 아니므로 실패로 표시하지 않는다."""


def _llm():
    # LLM 코드는 처음 쓸 때 불러온다 (LLM 을 안 쓰는 실행에서는 불러오지 않음)
    from llm.ollama_test import summarize_and_classify

    return summarize_and_classify


def summarize_one(notice):
    """공지 1건을 요약·분류한다. 결과 dict 를 돌려준다.

    Ollama 연결 문제면 LLMUnavailable, 모델 응답 문제면 ValueError 를 낸다.
    """
    try:
        return _llm()(notice)
    except HTTPError as e:  # URLError 의 하위 종류라 먼저 잡는다. 예: 모델 이름이 틀려 404
        raise LLMUnavailable(f"Ollama 응답 오류 {e.code}: {e.reason}") from e
    except (URLError, ConnectionError, socket.timeout, TimeoutError) as e:
        raise LLMUnavailable(f"Ollama 연결 실패: {e}") from e
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        raise ValueError(f"모델 응답을 해석할 수 없음: {e}") from e


def summarize_pending(limit=None):
    """요약 대기 공지를 오래된 것부터 limit 건 처리한다. (처리 완료 수, 실패 수)를 돌려준다.

    다른 곳에서 이미 처리 중이면 아무것도 하지 않는다.
    """
    global _ollama_ok
    if not config.LLM_ENABLED:
        return 0, 0
    if not _lock.acquire(blocking=False):
        return 0, 0

    limit = limit or config.SUMMARIZE_BATCH
    done = failed = 0
    try:
        notices = db.get_notices_to_summarize_new_first(limit=limit)
        if not notices:
            return 0, 0
        last_summary.update(started_at=_now(), finished_at=None, done=0, failed=0, error=None)

        for notice in notices:
            started = time.perf_counter()
            try:
                result = summarize_one(notice)
            except LLMUnavailable as e:
                if _ollama_ok is not False:
                    log.warning("%s. 요약을 멈추고 다음 차례에 다시 시도합니다.", e)
                _ollama_ok = False
                last_summary["error"] = str(e)
                break
            except ValueError as e:
                db.set_summary_status(notice["id"], "failed")
                failed += 1
                log.warning("요약 실패 [%d] %s: %s", notice["post_no"], notice["title"], e)
                continue

            if _ollama_ok is not True:
                log.info("Ollama 연결 확인")
            _ollama_ok = True
            db.save_ai_result(notice["id"], result)
            done += 1
            log.info(
                "요약 [%d] %s -> %s (%.1f초)",
                notice["post_no"], notice["title"], result.get("category"), time.perf_counter() - started,
            )
            last_summary.update(done=done, failed=failed)

        last_summary.update(finished_at=_now(), done=done, failed=failed,
                            pending_left=db.count_summary_status().get("pending", 0))
        return done, failed
    finally:
        _lock.release()


def summarize_all():
    """대기 공지가 없어질 때까지 처리한다 (명령줄용). Ollama 에 연결할 수 없으면 멈춘다."""
    total_done = total_failed = 0
    while True:
        done, failed = summarize_pending()
        total_done += done
        total_failed += failed
        if done + failed == 0:
            break
    log.info("요약 끝: 완료 %d건, 실패 %d건, 남은 대기 %d건",
             total_done, total_failed, db.count_summary_status().get("pending", 0))
    return total_done, total_failed


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")
