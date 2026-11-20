"""서버 설정 값."""

import os
from pathlib import Path

# 저장소 최상위 폴더
ROOT = Path(__file__).resolve().parent.parent

# DB 파일 위치. 기본은 database 모듈이 정한 위치(database/notices.db).
# 시험할 때만 환경 변수 NOTIF_DB_PATH 로 다른 파일을 쓴다.
DB_PATH = os.environ.get("NOTIF_DB_PATH")

HOST = os.environ.get("NOTIF_HOST", "127.0.0.1")
PORT = int(os.environ.get("NOTIF_PORT", "5000"))

# 크롤링 주기(분)
CRAWL_INTERVAL_MINUTES = 10

# DB가 비어 있을 때 처음 가져올 기간(일). 1년치 약 500건, 10초 간격이라 약 1시간 30분 걸린다.
FIRST_RUN_DAYS = 365

# 작성된 지 이 일수가 넘은 글은 새로 저장돼도 알림을 보내지 않는다.
NOTIFY_MAX_AGE_DAYS = 3

# 화면(React 개발 서버) 주소. 이 주소에서 오는 요청만 허용한다.
CORS_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}

# 목록 한 페이지 기본/최대 개수
PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
