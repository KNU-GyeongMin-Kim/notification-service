"""새 공지를 찾아 본문까지 가져오는 크롤러 진입점.

다른 모듈에서 쓸 때:
    from crawler.crawl import crawl_new
    notices = crawl_new(last_post_no=29515)

명령줄에서 시험할 때 (저장소 최상위 폴더에서):
    python -m crawler.crawl
    python -m crawler.crawl --last 29515 --out notices.json
"""

import argparse
import json
import logging
from datetime import datetime

from . import board, config

log = logging.getLogger(__name__)


def find_new_posts(last_post_no=None):
    """목록 페이지를 넘겨가며 last_post_no 보다 큰 글번호의 글을 찾는다.

    last_post_no 가 None 이면 첫 실행으로 보고 FIRST_RUN_PAGES 만큼만 가져온다.
    돌려주는 목록은 오래된 글부터 정렬되어 있다.
    """
    max_pages = config.FIRST_RUN_PAGES if last_post_no is None else config.MAX_PAGES
    found = {}

    for page in range(1, max_pages + 1):
        rows = board.fetch_list(page)
        if not rows:
            break

        reached_old = False
        for row in rows:
            if last_post_no is None or row["post_no"] > last_post_no:
                found[row["post_no"]] = row
            elif not row["pinned"]:
                # 고정 공지가 아닌 글 중 이미 가진 글이 나오면, 그 뒤는 모두 이전 글이다.
                reached_old = True

        if reached_old:
            break
    else:
        if last_post_no is not None:
            log.warning("%d페이지까지 봤지만 마지막 글번호(%s)에 닿지 못했습니다.", max_pages, last_post_no)

    return [found[no] for no in sorted(found)]


def crawl_new(last_post_no=None):
    """새 글을 찾고 본문까지 가져와 공지 목록을 돌려준다.

    공지 하나의 형식은 crawler/README.md 의 "넘겨주는 데이터 형식"을 따른다.
    본문 가져오기에 실패한 글은 건너뛰고 기록만 남긴다. 다음 실행 때 다시 시도된다.
    """
    notices = []
    for row in find_new_posts(last_post_no):
        try:
            detail = board.fetch_detail(row["post_no"])
        except Exception:
            log.exception("본문 가져오기 실패: %s", row["url"])
            # 이 글보다 뒤의 글을 저장하면 마지막 글번호가 앞서 나가 이 글을 영영 놓치므로 여기서 멈춘다.
            break

        notices.append(
            {
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
        )
        log.info("수집: [%d] %s", row["post_no"], notices[-1]["title"])

    return notices


def main():
    parser = argparse.ArgumentParser(description="학부 공지사항 새 글 수집")
    parser.add_argument("--last", type=int, default=None, help="이미 저장한 마지막 글번호 (없으면 첫 실행)")
    parser.add_argument("--out", default=None, help="결과를 저장할 JSON 파일 경로 (없으면 화면에 출력)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    notices = crawl_new(args.last)
    text = json.dumps(notices, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        log.info("%d건을 %s 에 저장했습니다.", len(notices), args.out)
    else:
        print(text)


if __name__ == "__main__":
    main()
