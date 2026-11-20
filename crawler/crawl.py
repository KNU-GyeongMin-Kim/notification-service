"""새 공지를 찾아 본문까지 가져오는 크롤러 진입점.

수집 방식은 두 가지다.
- 기간 수집 (crawl_since): 최근 N일 안에 올라온 글을 모두 가져온다. 처음 DB를 채울 때 쓴다.
- 새 글 수집 (crawl_new): 마지막으로 저장한 글번호 이후의 글만 가져온다. 10분마다 쓴다.

다른 모듈에서 쓸 때:
    from crawler.crawl import crawl_new, crawl_since
    notices = crawl_new(last_post_no=29515)
    for notice in crawl_since(days=365, skip=db.notice_exists):
        db.add_notice(notice)

명령줄에서 시험할 때 (저장소 최상위 폴더에서):
    python -m crawler.crawl --last 29515
    python -m crawler.crawl --days 7 --out notices.json
"""

import argparse
import json
import logging
from datetime import date, datetime, timedelta

from . import board, config

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- 목록에서 대상 글 고르기


def find_posts(last_post_no=None, since=None, max_pages=config.MAX_PAGES):
    """목록 페이지를 넘겨가며 대상 글을 고른다. 최신 글부터 돌려준다.

    - last_post_no: 이 글번호보다 큰 글만
    - since: 이 날짜(date) 이후에 올라온 글만

    고정 공지가 아닌 글 중 조건을 벗어난 글이 나오면, 그 뒤는 모두 더 오래된 글이므로 멈춘다.
    """
    found = {}
    for page in range(1, max_pages + 1):
        rows = board.fetch_list(page)
        if not rows:
            break

        reached_end = False
        for row in rows:
            if _is_target(row, last_post_no, since):
                found[row["post_no"]] = row
            elif not row["pinned"]:
                reached_end = True

        if reached_end:
            break
    else:
        log.warning("목록 %d페이지까지 봤지만 끝에 닿지 못했습니다. 한도를 늘려야 할 수 있습니다.", max_pages)

    return [found[no] for no in sorted(found, reverse=True)]


def _is_target(row, last_post_no, since):
    if last_post_no is not None and row["post_no"] <= last_post_no:
        return False
    if since is not None and _list_date(row) < since:
        return False
    return True


def _list_date(row):
    """목록의 작성일('2026-11-13')을 date로. 읽을 수 없으면 아주 옛날로 본다."""
    try:
        return date.fromisoformat(row["date"][:10])
    except ValueError:
        return date.min


# ---------------------------------------------------------------- 본문까지 가져오기


def fetch_notice(row):
    """목록 한 줄의 상세 페이지를 읽어 공지 dict 를 만든다."""
    detail = board.fetch_detail(row["post_no"])
    notice = {
        "post_no": row["post_no"],
        "title": detail["title"] or row["title"],
        "date": detail["posted_at"] or row["date"],
        "url": row["url"],
        "content": detail["content"],
        "board_category": detail["board_category"] or row["board_category"],
        "images": detail["images"],
        "attachments": detail["attachments"],
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    log.info("수집: [%d] %s %s", notice["post_no"], notice["date"], notice["title"])
    return notice


def crawl_since(days, skip=None, max_pages=config.BACKFILL_MAX_PAGES):
    """최근 days일 안에 올라온 글을 최신 글부터 하나씩 내준다 (제너레이터).

    - skip: 글번호를 받아 True 를 돌려주면 건너뛴다. 이미 저장한 글을 다시 읽지 않게 할 때 쓴다.
      (db.notice_exists 를 넘기면, 중간에 멈춰도 다시 실행했을 때 남은 글만 가져온다)
    - 오래 걸리므로 한 건씩 내준다. 받는 쪽에서 바로 저장하면 중간에 멈춰도 그때까지는 남는다.
    - 본문 가져오기에 실패한 글은 건너뛰고 기록만 남긴다. 다시 실행하면 그 글을 다시 시도한다.
    """
    since = date.today() - timedelta(days=days)
    rows = find_posts(since=since, max_pages=max_pages)
    if skip is not None:
        rows = [r for r in rows if not skip(r["post_no"])]
    minutes = -(-len(rows) * config.REQUEST_DELAY // 60)  # 올림
    log.info("%s 이후 글 중 가져올 글 %d건 (예상 약 %d분)", since, len(rows), minutes)

    for row in rows:
        try:
            yield fetch_notice(row)
        except Exception:
            log.exception("본문 가져오기 실패, 건너뜀: %s", row["url"])


def crawl_new(last_post_no):
    """last_post_no 보다 새 글을 본문까지 가져와 목록으로 돌려준다. 오래된 글부터.

    본문 가져오기에 실패하면 그 글에서 멈춘다. 뒤의 글만 저장되면 마지막 글번호가 앞서 나가
    실패한 글을 영영 놓치기 때문이다. 다음 실행 때 그 글부터 다시 시도된다.
    """
    notices = []
    for row in reversed(find_posts(last_post_no=last_post_no)):
        try:
            notices.append(fetch_notice(row))
        except Exception:
            log.exception("본문 가져오기 실패: %s", row["url"])
            break
    return notices


# ---------------------------------------------------------------- 명령줄 시험


def main():
    parser = argparse.ArgumentParser(description="학부 공지사항 수집 (시험용, DB에 저장하지 않음)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--last", type=int, help="이 글번호보다 새 글만")
    group.add_argument("--days", type=int, help="최근 N일 안에 올라온 글")
    parser.add_argument("--out", default=None, help="결과를 저장할 JSON 파일 경로 (없으면 화면에 출력)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    notices = crawl_new(args.last) if args.last is not None else list(crawl_since(args.days))
    text = json.dumps(notices, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        log.info("%d건을 %s 에 저장했습니다.", len(notices), args.out)
    else:
        print(text)


if __name__ == "__main__":
    main()
