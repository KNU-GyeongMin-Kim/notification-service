"""공지 알림 이메일 만들기와 보내기.

설정은 저장소 최상위의 .env 파일에서 읽는다 (.env.example 참고, .env 는 저장소에 올리지 않는다).
SMTP 계정이 없거나 MAIL_DRY_RUN=1 이면 실제로 보내지 않고 server/outbox/ 에 .eml 파일로 저장한다.

시험 (저장소 최상위 폴더에서):
    python -m server.mailer --post 29519                    # 메일 미리보기만 (outbox 에 저장)
    python -m server.mailer --post 29519 --to me@gmail.com  # 실제로 보내기 (.env 설정 필요)
"""

import argparse
import html
import logging
import os
import re
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path

from dotenv import load_dotenv

from . import config

log = logging.getLogger(__name__)

load_dotenv(config.ROOT / ".env")

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
MAIL_FROM_NAME = os.environ.get("MAIL_FROM_NAME", "학과 공지 알림")
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")  # 우리 서비스 주소 (있으면 메일에 링크)
DRY_RUN = os.environ.get("MAIL_DRY_RUN", "0") == "1" or not (SMTP_USER and SMTP_PASSWORD)

OUTBOX = Path(__file__).resolve().parent / "outbox"


# ---------------------------------------------------------------- 키워드 대조


def _normalize(text):
    """띄어쓰기를 없애고 소문자로. '국가 장학금'과 '국가장학금'을 같게 본다."""
    return re.sub(r"\s+", "", text or "").lower()


def match_keywords(notice, keywords):
    """공지 제목, 본문, 요약에 들어 있는 키워드 목록을 돌려준다 (등록 순서 유지)."""
    haystack = _normalize(" ".join([notice.get("title") or "", notice.get("content") or "", notice.get("summary") or ""]))
    return [k for k in keywords if _normalize(k) and _normalize(k) in haystack]


# ---------------------------------------------------------------- 메일 만들기


def build_notice_email(notice, to, matched_keywords=()):
    """공지 1건으로 알림 메일(EmailMessage)을 만든다. 글자 버전과 HTML 버전을 같이 넣는다.

    notice: DB 공지 dict (database.db 가 돌려주는 형태)
    원문 링크는 요약이 틀릴 수 있으므로 항상 넣는다.
    """
    title = notice["title"]
    rows = _info_rows(notice, matched_keywords)
    summary = notice.get("summary")
    no_body = not (notice.get("content") or "").strip()
    detail_url = f"{SITE_URL}/notices/{notice['post_no']}" if SITE_URL else None

    msg = EmailMessage()
    msg["Subject"] = f"[학과 공지] {title}"
    msg["From"] = formataddr((MAIL_FROM_NAME, SMTP_USER or "noreply@localhost"))
    msg["To"] = to
    msg["Message-ID"] = make_msgid(domain="notif.local")

    # 글자 버전 (HTML을 못 보는 메일 프로그램용)
    lines = [title, ""]
    lines += [f"{label}: {value}" for label, value in rows]
    if summary:
        lines += ["", "[AI 요약]", summary]
    if no_body:
        lines += ["", "본문이 이미지나 첨부파일로만 되어 있습니다. 원문에서 확인해 주세요."]
    lines += ["", f"원문 보기: {notice['url']}"]
    if detail_url:
        lines.append(f"서비스에서 보기: {detail_url}")
    lines += ["", "AI 요약은 틀릴 수 있으니 중요한 내용은 원문을 확인해 주세요.", _footer_text()]
    msg.set_content("\n".join(lines))

    # HTML 버전
    e = html.escape
    info_html = "".join(
        f'<tr><td style="padding:4px 12px 4px 0;color:#666;white-space:nowrap">{e(label)}</td>'
        f'<td style="padding:4px 0">{e(value)}</td></tr>'
        for label, value in rows
    )
    parts = [
        '<div style="font-family:sans-serif;max-width:600px;line-height:1.6;color:#222">',
        f'<h2 style="font-size:18px;margin:0 0 12px">{e(title)}</h2>',
        f'<table style="font-size:14px;border-collapse:collapse;margin-bottom:12px">{info_html}</table>',
    ]
    if summary:
        parts.append(
            '<div style="background:#f4f6fb;border-radius:8px;padding:12px 16px;margin-bottom:12px">'
            f'<div style="font-weight:600;margin-bottom:4px">AI 요약</div>'
            f'<div style="white-space:pre-line">{e(summary)}</div></div>'
        )
    if no_body:
        parts.append('<p style="color:#666">본문이 이미지나 첨부파일로만 되어 있습니다. 원문에서 확인해 주세요.</p>')
    parts.append(
        f'<p><a href="{e(notice["url"])}" style="display:inline-block;background:#5b5bd6;color:#fff;'
        'padding:8px 16px;border-radius:6px;text-decoration:none">원문 보기</a>'
    )
    if detail_url:
        parts.append(f' &nbsp;<a href="{e(detail_url)}">서비스에서 보기</a>')
    parts.append("</p>")
    parts.append(
        '<p style="font-size:12px;color:#999">AI 요약은 틀릴 수 있으니 중요한 내용은 원문을 확인해 주세요.<br>'
        f"{e(_footer_text())}</p></div>"
    )
    msg.add_alternative("".join(parts), subtype="html")
    return msg


def _info_rows(notice, matched_keywords):
    rows = []
    if matched_keywords:
        rows.append(("관심 키워드", ", ".join(matched_keywords)))
    category = " / ".join(c for c in (notice.get("category"), notice.get("board_category")) if c)
    if category:
        rows.append(("분류", category))
    if notice.get("published_at"):
        rows.append(("게시일", notice["published_at"]))
    if notice.get("application_period"):
        rows.append(("신청 기간", notice["application_period"]))
    if notice.get("target"):
        rows.append(("대상", notice["target"]))
    if notice.get("attachments"):
        rows.append(("첨부파일", f"{len(notice['attachments'])}개 (원문에서 받기)"))
    return rows


def _footer_text():
    where = f"{SITE_URL}/settings" if SITE_URL else "서비스의 알림 설정"
    return f"이 메일은 등록한 관심 키워드에 맞는 새 공지가 올라와 보내드렸습니다. 알림 끄기: {where}"


# ---------------------------------------------------------------- 보내기


class Mailer:
    """여러 통을 보낼 때 SMTP 연결 하나를 다시 쓴다.

        with Mailer() as m:
            m.send(msg1)
            m.send(msg2)
    """

    def __init__(self, dry_run=None):
        self.dry_run = DRY_RUN if dry_run is None else dry_run
        self._smtp = None

    def __enter__(self):
        if not self.dry_run:
            self._smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
            self._smtp.starttls(context=ssl.create_default_context())
            self._smtp.login(SMTP_USER, SMTP_PASSWORD)
        return self

    def __exit__(self, *exc):
        if self._smtp is not None:
            try:
                self._smtp.quit()
            except smtplib.SMTPException:
                pass
            self._smtp = None

    def send(self, msg):
        """메일 1통을 보낸다. 성공하면 True, 실패하면 기록만 남기고 False."""
        try:
            if self.dry_run:
                path = _save_to_outbox(msg)
                log.info("[미리보기] %s -> %s (%s)", msg["Subject"], msg["To"], path)
            else:
                self._smtp.send_message(msg)
                log.info("발송: %s -> %s", msg["Subject"], msg["To"])
            return True
        except Exception:
            log.exception("발송 실패: %s -> %s", msg["Subject"], msg["To"])
            return False


def send_email(msg, dry_run=None):
    """메일 1통만 보낼 때 쓰는 간단한 함수."""
    try:
        with Mailer(dry_run=dry_run) as m:
            return m.send(msg)
    except Exception:
        log.exception("메일 서버 연결 실패 (%s:%s)", SMTP_HOST, SMTP_PORT)
        return False


def _save_to_outbox(msg):
    OUTBOX.mkdir(exist_ok=True)
    safe_to = re.sub(r"[^0-9A-Za-z@._-]", "_", str(msg["To"]))
    path = OUTBOX / f"{datetime.now():%Y%m%d-%H%M%S-%f}_{safe_to}.eml"
    path.write_bytes(msg.as_bytes())
    return path


# ---------------------------------------------------------------- 명령줄 시험


def main():
    from database import db

    parser = argparse.ArgumentParser(description="공지 알림 메일 시험")
    parser.add_argument("--post", type=int, required=True, help="DB에 있는 공지의 게시판 글번호")
    parser.add_argument("--to", default=None, help="받는 주소. 없으면 미리보기만 (outbox 에 저장)")
    parser.add_argument("--keywords", default="", help="쉼표로 구분한 키워드 (대조 결과를 메일에 표시)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if config.DB_PATH:
        db.DB_PATH = config.DB_PATH

    notice = db.get_notice_by_post_no(args.post)
    if notice is None:
        raise SystemExit(f"DB에 {args.post}번 공지가 없습니다. 먼저 수집해 주세요.")

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    matched = match_keywords(notice, keywords)
    if keywords:
        log.info("키워드 대조: %s 중 %s", keywords, matched or "맞는 것 없음")

    msg = build_notice_email(notice, args.to or "preview@example.com", matched)
    ok = send_email(msg, dry_run=True if args.to is None else None)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
