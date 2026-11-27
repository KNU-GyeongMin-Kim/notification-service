"""서버 설정 값."""

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

# 저장소 최상위 폴더
ROOT = Path(__file__).resolve().parent.parent

# .env 의 값을 환경 변수로 불러온다 (이미 있는 환경 변수가 우선)
load_dotenv(ROOT / ".env")

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

# LLM 요약. Ollama 주소와 모델은 llm/ollama_test.py 가 환경 변수 OLLAMA_URL, OLLAMA_MODEL 로 읽는다.
# NOTIF_LLM=0 이면 요약을 아예 하지 않는다.
LLM_ENABLED = os.environ.get("NOTIF_LLM", "1") != "0"
SUMMARIZE_INTERVAL_MINUTES = 2  # 요약 대기 공지를 확인하는 주기
SUMMARIZE_BATCH = 20            # 한 번에 처리할 최대 건수 (1건 약 4초)

# 화면(React 개발 서버) 주소. 이 주소에서 오는 요청만 허용한다.
CORS_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}

# 로그인 세션 쿠키 서명용 비밀 값. .env 에 SECRET_KEY 를 꼭 넣는다.
# 없으면 실행할 때마다 새로 만들어져서, 서버를 다시 켜면 모두 로그아웃된다.
SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
SECRET_KEY_FROM_ENV = bool(os.environ.get("SECRET_KEY"))
MIN_PASSWORD_LENGTH = 8

# 목록 한 페이지 기본/최대 개수
PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
