"""로그인과 사용자 설정 API (회원가입, 로그인, 내 정보, 키워드, 구독 분류, 저장한 공지).

로그인 상태는 Flask 세션 쿠키로 유지한다. 화면은 Vite proxy 로 같은 주소처럼 부르므로 쿠키가 그대로 오간다.
비밀번호는 werkzeug 로 해시를 만들어 DB에 저장하고, 원문은 어디에도 남기지 않는다.
API 설명은 server/README.md 참고.
"""

import re
from functools import wraps

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from database import db

from . import config

bp = Blueprint("auth", __name__, url_prefix="/api")

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MAX_KEYWORDS = 30
MAX_KEYWORD_LENGTH = 30


def _categories():
    # 세부 분류 목록은 LLM 쪽이 정한 것을 그대로 쓴다 (한 곳에서만 관리)
    from llm.ollama_test import CATEGORIES

    return CATEGORIES


# ---------------------------------------------------------------- 공통


def _error(message, status):
    return jsonify(error=message), status


def _body():
    return request.get_json(silent=True) or {}


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user_id = session.get("user_id")
        if user_id is None or db.get_user(user_id) is None:
            session.clear()
            return _error("로그인이 필요합니다.", 401)
        return view(user_id, *args, **kwargs)

    return wrapper


def user_to_dict(user):
    """화면에 보낼 사용자 정보. 비밀번호 해시는 절대 내보내지 않는다."""
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "notify_on": bool(user["notify_on"]),
        "created_at": user.get("created_at"),
        "keywords": db.list_keywords(user["id"]),
        "categories": db.list_subscriptions(user["id"]),
    }


def _notice_id(post_no):
    """게시판 글번호(화면의 공지 id)를 DB 내부 번호로. 없으면 None."""
    notice = db.get_notice_by_post_no(post_no)
    return notice["id"] if notice else None


# ---------------------------------------------------------------- 회원가입·로그인


@bp.post("/auth/signup")
def signup():
    data = _body()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    name = (data.get("name") or "").strip() or email.split("@")[0]

    if not EMAIL_RE.match(email):
        return _error("올바른 이메일 주소를 입력해 주세요.", 400)
    if len(password) < config.MIN_PASSWORD_LENGTH:
        return _error(f"비밀번호는 {config.MIN_PASSWORD_LENGTH}자 이상이어야 합니다.", 400)
    if len(name) > 30:
        return _error("이름은 30자 이하로 입력해 주세요.", 400)

    user_id = db.create_user(email, name, generate_password_hash(password))
    if user_id is None:
        return _error("이미 가입된 이메일입니다.", 409)

    session.clear()
    session["user_id"] = user_id
    session.permanent = True
    return jsonify(user_to_dict(db.get_user(user_id))), 201


@bp.post("/auth/login")
def login():
    data = _body()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    user = db.get_user_by_email(email)
    # 이메일이 없는 경우와 비밀번호가 틀린 경우를 같은 문구로 (가입 여부를 알려주지 않기 위해)
    if user is None or not user.get("password_hash") or not check_password_hash(user["password_hash"], password):
        return _error("이메일 또는 비밀번호가 올바르지 않습니다.", 401)

    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True
    return jsonify(user_to_dict(user))


@bp.post("/auth/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


# ---------------------------------------------------------------- 내 정보


@bp.get("/me")
@login_required
def me(user_id):
    return jsonify(user_to_dict(db.get_user(user_id)))


@bp.patch("/me")
@login_required
def update_me(user_id):
    data = _body()
    name = data.get("name")
    if name is not None:
        name = str(name).strip()
        if not name or len(name) > 30:
            return _error("이름은 1~30자로 입력해 주세요.", 400)
    notify_on = data.get("notify_on")
    if notify_on is not None and not isinstance(notify_on, bool):
        return _error("notify_on 은 true 또는 false 여야 합니다.", 400)
    db.update_user_settings(user_id, notify_on=notify_on, name=name)
    return jsonify(user_to_dict(db.get_user(user_id)))


# ---------------------------------------------------------------- 키워드


@bp.get("/me/keywords")
@login_required
def get_keywords(user_id):
    return jsonify(keywords=db.list_keywords(user_id))


@bp.put("/me/keywords")
@login_required
def replace_keywords(user_id):
    """키워드 목록 전체를 바꾼다. {"keywords": ["장학금", "인턴"]}"""
    words = _body().get("keywords")
    if not isinstance(words, list):
        return _error('{"keywords": [...]} 형식으로 보내 주세요.', 400)
    cleaned = []
    for w in words:
        w = str(w).strip()
        if w and w not in cleaned:
            cleaned.append(w)
    if len(cleaned) > MAX_KEYWORDS or any(len(w) > MAX_KEYWORD_LENGTH for w in cleaned):
        return _error(f"키워드는 {MAX_KEYWORDS}개, 한 개에 {MAX_KEYWORD_LENGTH}자까지 등록할 수 있습니다.", 400)

    current = db.list_keywords(user_id)
    for w in current:
        if w not in cleaned:
            db.remove_keyword(user_id, w)
    for w in cleaned:
        if w not in current:
            db.add_keyword(user_id, w)
    return jsonify(keywords=db.list_keywords(user_id))


@bp.post("/me/keywords")
@login_required
def add_keyword(user_id):
    """키워드 하나 추가. {"word": "장학금"}"""
    word = str(_body().get("word") or "").strip()
    if not word or len(word) > MAX_KEYWORD_LENGTH:
        return _error(f"키워드는 1~{MAX_KEYWORD_LENGTH}자로 입력해 주세요.", 400)
    if len(db.list_keywords(user_id)) >= MAX_KEYWORDS:
        return _error(f"키워드는 {MAX_KEYWORDS}개까지 등록할 수 있습니다.", 400)
    db.add_keyword(user_id, word)
    return jsonify(keywords=db.list_keywords(user_id))


@bp.delete("/me/keywords/<path:word>")
@login_required
def remove_keyword(user_id, word):
    db.remove_keyword(user_id, word)
    return jsonify(keywords=db.list_keywords(user_id))


# ---------------------------------------------------------------- 구독 분류


@bp.get("/me/categories")
@login_required
def get_categories(user_id):
    return jsonify(categories=db.list_subscriptions(user_id), available=_categories())


@bp.put("/me/categories")
@login_required
def replace_categories(user_id):
    """구독 분류 전체를 바꾼다. {"categories": ["장학", "취업·인턴"]}"""
    categories = _body().get("categories")
    if not isinstance(categories, list):
        return _error('{"categories": [...]} 형식으로 보내 주세요.', 400)
    allowed = _categories()
    wrong = [c for c in categories if c not in allowed]
    if wrong:
        return _error(f"없는 분류입니다: {', '.join(map(str, wrong))}. 가능한 값: {', '.join(allowed)}", 400)
    db.set_subscriptions(user_id, categories)
    return jsonify(categories=db.list_subscriptions(user_id), available=allowed)


# ---------------------------------------------------------------- 저장한 공지


@bp.get("/me/saved")
@login_required
def get_saved(user_id):
    from .app import notice_to_dict

    return jsonify(items=[notice_to_dict(n) for n in db.list_saved(user_id)])


@bp.put("/me/saved/<int(signed=True):post_no>")
@login_required
def save_notice(user_id, post_no):
    notice_id = _notice_id(post_no)
    if notice_id is None:
        return _error("공지를 찾을 수 없습니다.", 404)
    db.save_notice_for_user(user_id, notice_id)
    return jsonify(saved=True, id=post_no)


@bp.delete("/me/saved/<int(signed=True):post_no>")
@login_required
def unsave_notice(user_id, post_no):
    notice_id = _notice_id(post_no)
    if notice_id is not None:
        db.unsave_notice(user_id, notice_id)
    return jsonify(saved=False, id=post_no)
