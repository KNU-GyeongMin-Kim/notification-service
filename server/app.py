"""Flask API 서버. 화면(React)은 이 API로 데이터를 가져간다.

API 목록은 server/README.md 참고.
"""

import json

from flask import Flask, jsonify, request

import db

from . import config, jobs


def create_app():
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
        return jsonify(status="ok", notices=total, last_crawl=jobs.last_crawl)

    @app.get("/api/notices")
    def notices():
        page = max(request.args.get("page", 1, type=int), 1)
        size = min(max(request.args.get("size", config.PAGE_SIZE, type=int), 1), config.MAX_PAGE_SIZE)
        category = request.args.get("category") or None
        if category == "전체":
            category = None

        rows, total = db.list_notices(category=category, limit=size, offset=(page - 1) * size)
        return jsonify(items=[notice_to_dict(r) for r in rows], total=total, page=page, size=size)

    @app.get("/api/notices/<int:post_no>")
    def notice_detail(post_no):
        row = db.get_notice_by_post_no(post_no)
        if row is None:
            return jsonify(error="공지를 찾을 수 없습니다."), 404
        return jsonify(notice_to_dict(row, detail=True))

    @app.get("/api/categories")
    def categories():
        return jsonify([{"name": name, "count": cnt} for name, cnt in db.count_by_category()])

    @app.errorhandler(404)
    def not_found(e):
        return jsonify(error="없는 주소입니다."), 404

    return app


def notice_to_dict(row, detail=False):
    """DB 한 줄을 화면에 보낼 형태로 바꾼다. 공지 번호는 게시판 글번호(post_no)를 쓴다."""
    d = {
        "id": row["post_no"],
        "title": row["title"],
        "date": row["published_at"],
        "url": row["url"],
        "category": row["category"] or row["board_category"],
        "board_category": row["board_category"],
        "summary": row["summary"],
        "target": row["target"],
        "apply_period": row["apply_period"],
        "has_attachments": bool(_json_list(row["attachments"])),
    }
    if detail:
        d.update(
            content=row["content"],
            images=_json_list(row["images"]),
            attachments=_json_list(row["attachments"]),
            documents=_json_list(row["documents"]),
            fetched_at=row["fetched_at"],
        )
    return d


def _json_list(text):
    """DB에 JSON 글자로 저장된 목록을 파이썬 목록으로 되돌린다."""
    if not text:
        return []
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []
