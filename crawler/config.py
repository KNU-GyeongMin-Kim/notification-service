"""크롤러 설정 값."""

# 경북대학교 컴퓨터학부 학부 공지사항 게시판
BASE_URL = "https://aicollege.knu.ac.kr/bbs/board.php"
BO_TABLE = "sub6_1_a"

# 요청 사이 간격(초). 사이트 robots.txt 의 Crawl-delay 값(10초)을 따른다.
REQUEST_DELAY = 10

# 요청 제한 시간(초)
TIMEOUT = 15

USER_AGENT = "NotifServiceCrawler/0.1 (student project)"

# 새 글 수집 때 최대로 넘겨볼 목록 페이지 수 (한 페이지에 15개)
MAX_PAGES = 5

# 기간 수집 때 최대로 넘겨볼 목록 페이지 수. 1년치가 약 34페이지(2026-11 기준).
BACKFILL_MAX_PAGES = 60
