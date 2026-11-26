import argparse
import json
import logging
from pathlib import Path

from crawler import board, config
from crawler.crawl import fetch_notice


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--out", default="llm/test.json")
    args = parser.parse_args()
    if args.count < 1:
        raise ValueError("count must be positive")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    candidates = {}
    for page in range(1, config.BACKFILL_MAX_PAGES + 1):
        rows = board.fetch_list(page)
        if not rows:
            break
        for row in rows:
            if not row["pinned"]:
                candidates[row["post_no"]] = row
        logging.info("목록 %d페이지 확인, 새 글 후보 %d건", page, len(candidates))
        if len(candidates) >= args.count:
            break

    selected = sorted(candidates.values(), key=lambda row: row["post_no"], reverse=True)[:args.count]
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    notices = []
    for index, row in enumerate(selected, start=1):
        try:
            notice = fetch_notice(row)
            notice.pop("images", None)
            notices.append(notice)
            output_path.write_text(json.dumps(notices, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            logging.info("상세 수집 %d/%d, post_no=%d", index, len(selected), row["post_no"])
        except Exception:
            logging.exception("상세 수집 실패, post_no=%d", row["post_no"])

    logging.info("완료: %d/%d건 저장, 파일=%s", len(notices), args.count, output_path)


if __name__ == "__main__":
    main()
