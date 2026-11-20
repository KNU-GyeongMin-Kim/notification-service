"""서버 설정 값."""

import os
from pathlib import Path

# 저장소 최상위 폴더
ROOT = Path(__file__).resolve().parent.parent

# DB 파일 위치. 실행한 폴더와 상관없이 항상 저장소 최상위의 notices.db 를 쓴다.
DB_PATH = os.environ.get("NOTIF_DB_PATH", str(ROOT / "notices.db"))

HOST = os.environ.get("NOTIF_HOST", "127.0.0.1")
PORT = int(os.environ.get("NOTIF_PORT", "5000"))

# 크롤링 주기(분)
CRAWL_INTERVAL_MINUTES = 10

# 화면(React 개발 서버) 주소. 이 주소에서 오는 요청만 허용한다.
CORS_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}

# 목록 한 페이지 기본/최대 개수
PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
