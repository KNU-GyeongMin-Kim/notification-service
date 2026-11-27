"""Flask API 서버. 화면(React)은 이 API로 데이터를 가져간다.

API 목록은 server/README.md 참고.
"""

from flask import Flask, jsonify, request

from database import db

from . import config, jobs, summarizer


def create_app():
    if config.DB_PATH:  # 지정하지 않으면 database 모듈의 기본 위치를 쓴다
        db.DB_PATH = config.DB_PATH
    db.init_db()

    app = Flask(__name__)
    app.json.ensure_ascii = False  # 한글을 \uXXXX 로 바꾸지 않고 그대로 보낸다

    @app.after_request
    def allow_frontend(resp):
        # React 개발 서버(5173 포트)에서 이 서버(5000 포트)로 요청할 수 있게 허용
        origin = request.headers.get("Origin")
        if origin in config.CORS_ORIGINS:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        return resp

    @app.get("/api/health")
    def health():
        _, total = db.list_notices(limit=1)
        return jsonify(
            status="ok",
            notices=total,
            summary_status=db.count_summary_status(),
            last_crawl=jobs.last_crawl,
            last_summary=summarizer.last_summary,
        )

    @app.get("/api/notices")
    def notices():
        page = max(request.args.get("page", 1, type=int), 1)
        size = min(max(request.args.get("size", config.PAGE_SIZE, type=int), 1), config.MAX_PAGE_SIZE)
        rows, total = db.list_notices(
            category=_filter_value("category"),
            board_category=_filter_value("board_category"),
            limit=size,
            offset=(page - 1) * size,
        )
        return jsonify(items=[notice_to_dict(r) for r in rows], total=total, page=page, size=size)

    @app.get("/api/notices/<int:post_no>")
    def notice_detail(post_no):
        row = db.get_notice_by_post_no(post_no)
        if row is None:
            return jsonify(error="공지를 찾을 수 없습니다."), 404
        return jsonify(notice_to_dict(row, detail=True))

    @app.get("/api/categories")
    def categories():
        def counts(column):
            return [{"name": name, "count": cnt} for name, cnt in db.count_by_category(column)]

        return jsonify(category=counts("category"), board_category=counts("board_category"))

    @app.errorhandler(404)
    def not_found(e):
        return jsonify(error="없는 주소입니다."), 404

    return app


def _filter_value(name):
    """목록 필터 값. 비어 있거나 '전체'면 거르지 않는다."""
    value = request.args.get(name) or None
    return None if value == "전체" else value


def notice_to_dict(row, detail=False):
    """DB 공지(dict)를 화면에 보낼 형태로 바꾼다. 공지 번호는 게시판 글번호(post_no)를 쓴다."""
    d = {
        "id": row["post_no"],
        "title": row["title"],
        "date": row["published_at"],
        "url": row["url"],
        "category": row["category"],              # 세부 분류 (AI). 요약 전에는 null
        "board_category": row["board_category"],  # 사이트 분류
        "summary": row["summary"],
        "summary_status": row["summary_status"],
        "target": row["target"],
        "application_period": row["application_period"],
        "has_attachments": bool(row["attachments"]),
    }
    if detail:
        d.update(
            content=row["content"],
            images=row["images"],
            attachments=row["attachments"],
            documents=row["documents"],
            fetched_at=row["fetched_at"],
        )
    return d
