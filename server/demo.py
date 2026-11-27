"""시연용 공지: 발표 당일 새 공지가 없어도 "새 공지 -> 요약 -> 알림 메일"을 보여주기 위한 도구.

시연용 공지는 음수 글번호(-1, -2, ...)로 저장되어 실제 게시판 글과 섞이지 않고, 새 글 수집에도 영향을 주지 않는다.
제목 앞에 [시연용]이 붙는다.

사용법 (저장소 최상위 폴더에서):
    python -m server.demo list-presets             # 준비된 예시 공지 목록
    python -m server.demo add 장학                  # 예시 공지를 넣고 바로 요약 -> 알림까지 실행
    python -m server.demo add --title "제목" --content "본문" [--board-category 일반공지]
    python -m server.demo add 장학 --no-run         # 넣기만 하고 요약·알림은 서버 주기에 맡김
    python -m server.demo list                      # 들어 있는 시연용 공지와 상태
    python -m server.demo clear                     # 시연용 공지와 발송 기록 모두 삭제 (실제 공지는 그대로)
"""

import argparse
import logging
from datetime import datetime

from database import db

from . import config, notifier, summarizer

log = logging.getLogger(__name__)

BOARD_URL = "https://aicollege.knu.ac.kr/bbs/board.php?bo_table=sub6_1_a"
TAG = "[시연용] "

# 예시 공지. 실제 공지가 아니며 기관명·날짜는 가상이다.
PRESETS = {
    "장학": {
        "title": "2027학년도 1학기 OO장학재단 장학생 선발 안내",
        "board_category": "장학",
        "content": (
            "2027학년도 1학기 OO장학재단 장학생을 아래와 같이 선발하오니 희망 학생은 기한 내 신청하기 바랍니다.\n\n"
            "1. 지원 대상: 컴퓨터학부 2~4학년 재학생 (직전 학기 평점 3.0 이상)\n"
            "2. 장학 금액: 1인당 등록금 전액\n"
            "3. 신청 기간: 2026.12.1.(화) ~ 2026.12.12.(토) 18:00\n"
            "4. 제출 서류: 장학금 신청서, 성적증명서, 자기소개서\n"
            "5. 제출 방법: 학부사무실 방문 제출\n\n"
            "※ 문의: 학부사무실"
        ),
    },
    "공모전": {
        "title": "제5회 캠퍼스 AI 해커톤 참가팀 모집",
        "board_category": "일반공지",
        "content": (
            "생성형 AI를 활용한 캠퍼스 문제 해결 해커톤 참가팀을 모집합니다.\n\n"
            "- 참가 대상: 재학생 2~4인 팀\n"
            "- 접수 기간: 2026.12.1. ~ 2026.12.10.\n"
            "- 본선 일정: 2026.12.19.(토) ~ 12.20.(일), 무박 2일\n"
            "- 시상: 대상 1팀, 최우수상 2팀, 우수상 3팀\n"
            "- 신청 방법: 온라인 신청서 제출"
        ),
    },
    "취업": {
        "title": "2026 동계 SW기업 현장실습(인턴십) 참가자 모집",
        "board_category": "일반공지",
        "content": (
            "동계방학 기간 SW기업 현장실습 참가자를 모집합니다.\n\n"
            "- 대상: 3~4학년 재학생\n"
            "- 실습 기간: 2026.12.22. ~ 2027.2.20. (8주)\n"
            "- 혜택: 실습지원비 지급, 현장실습 학점 인정\n"
            "- 신청 기간: 2026.12.1. ~ 2026.12.8.\n"
            "- 제출 서류: 참가신청서, 이력서"
        ),
    },
    "이미지": {
        "title": "OO기업 채용설명회 홍보 (본문 이미지만 있는 공지 예시)",
        "board_category": "일반공지",
        "content": "",
    },
}


def add_demo_notice(title, content, board_category="일반공지"):
    """시연용 공지 1건을 넣는다. 저장된 공지 dict 를 돌려준다."""
    post_no = db.next_demo_post_no()
    now = datetime.now()
    db.add_notice(
        {
            "post_no": post_no,
            "title": TAG + title,
            "date": now.strftime("%Y-%m-%d %H:%M"),
            "url": BOARD_URL,
            "content": content,
            "board_category": board_category,
            "images": [],
            "attachments": [],
            "collected_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        },
        is_initial=False,  # 새 공지로 취급해서 알림 대상이 되게
    )
    return db.get_notice_by_post_no(post_no)


def run_pipeline():
    """요약 -> 알림을 바로 한 번 실행한다."""
    done, failed = summarizer.summarize_pending() if config.LLM_ENABLED else (0, 0)
    notices, sent, mail_failed = notifier.notify_pending()
    return {"summarized": done, "summary_failed": failed, "notified_notices": notices, "sent": sent, "mail_failed": mail_failed}


def _print_notice(n):
    print(f"  [{n['post_no']}] {n['title']}")
    print(f"      게시일 {n['published_at']} | 사이트 분류 {n['board_category']} | 세부 분류 {n['category'] or '-'}")
    print(f"      요약 상태 {n['summary_status']} | 알림 {'완료' if n['notified'] else '대기'}")
    if n.get("summary"):
        print(f"      요약: {n['summary']}")


def main():
    parser = argparse.ArgumentParser(description="시연용 공지 도구")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="시연용 공지 넣기")
    add.add_argument("preset", nargs="?", choices=list(PRESETS), help="예시 공지 이름")
    add.add_argument("--title", help="직접 쓴 제목 (preset 대신)")
    add.add_argument("--content", default="", help="직접 쓴 본문")
    add.add_argument("--board-category", default="일반공지", help="사이트 분류")
    add.add_argument("--no-run", action="store_true", help="넣기만 하고 요약·알림은 실행하지 않음")

    sub.add_parser("list", help="시연용 공지 목록")
    sub.add_parser("list-presets", help="예시 공지 목록")
    sub.add_parser("clear", help="시연용 공지와 발송 기록 모두 삭제")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    if config.DB_PATH:
        db.DB_PATH = config.DB_PATH
    db.init_db()

    if args.command == "list-presets":
        for name, p in PRESETS.items():
            print(f"  {name}: {p['title']}")
        return

    if args.command == "list":
        notices = db.list_demo_notices()
        print(f"시연용 공지 {len(notices)}건")
        for n in notices:
            _print_notice(n)
        return

    if args.command == "clear":
        print(f"시연용 공지 {db.delete_demo_notices()}건을 지웠습니다. (실제 공지는 그대로)")
        return

    # add
    if args.title:
        notice = add_demo_notice(args.title, args.content, args.board_category)
    elif args.preset:
        p = PRESETS[args.preset]
        notice = add_demo_notice(p["title"], p["content"], p["board_category"])
    else:
        parser.error("예시 이름(예: 장학)이나 --title 중 하나를 주세요. 목록: python -m server.demo list-presets")
    print(f"시연용 공지를 넣었습니다: [{notice['post_no']}] {notice['title']}")

    if args.no_run:
        print("요약·알림은 실행 중인 서버가 2분 안에 처리합니다.")
        return

    result = run_pipeline()
    print(
        f"요약 {result['summarized']}건 (실패 {result['summary_failed']}) | "
        f"알림 공지 {result['notified_notices']}건, 메일 {result['sent']}통 발송 (실패 {result['mail_failed']})"
    )
    _print_notice(db.get_notice_by_post_no(notice["post_no"]))


if __name__ == "__main__":
    main()
