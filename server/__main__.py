"""서버 실행 진입점. 저장소 최상위 폴더에서 실행한다.

    python -m server                 # API 서버 + 10분마다 자동 수집
    python -m server --no-scheduler  # API 서버만 (자동 수집 끔)
    python -m server --crawl-once    # 수집 한 번만 하고 끝냄
"""

import argparse
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from . import config, jobs
from .app import create_app


def main():
    parser = argparse.ArgumentParser(description="학과 공지 알림 서비스 서버")
    parser.add_argument("--no-scheduler", action="store_true", help="자동 수집을 켜지 않는다")
    parser.add_argument("--crawl-once", action="store_true", help="수집을 한 번만 하고 끝낸다")
    parser.add_argument("--port", type=int, default=config.PORT)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

    app = create_app()  # DB 준비도 여기서 한다

    if args.crawl_once:
        jobs.crawl_job()
        return

    if not args.no_scheduler:
        scheduler = BackgroundScheduler(timezone="Asia/Seoul")
        scheduler.add_job(
            jobs.crawl_job,
            "interval",
            minutes=config.CRAWL_INTERVAL_MINUTES,
            next_run_time=datetime.now(),  # 서버를 켜자마자 한 번 수집
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()

    # use_reloader=False: 자동 재시작 기능을 켜면 프로세스가 둘이 되어 수집이 두 번 돈다
    app.run(host=config.HOST, port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
