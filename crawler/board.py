"""게시판 페이지를 가져오고 필요한 정보를 뽑아내는 함수 모음.

가져오기(fetch_*)와 뽑아내기(parse_*)를 나눠두어,
저장해 둔 HTML 파일로도 뽑아내기 부분을 시험할 수 있다.
"""

import logging
import re
import time
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

from . import config

log = logging.getLogger(__name__)

_session = requests.Session()
_session.headers["User-Agent"] = config.USER_AGENT
_last_request_at = 0.0


def _get(params):
    """요청 간격을 지키며 페이지를 가져온다."""
    global _last_request_at
    wait = config.REQUEST_DELAY - (time.monotonic() - _last_request_at)
    if wait > 0:
        time.sleep(wait)

    try:
        resp = _session.get(config.BASE_URL, params=params, timeout=config.TIMEOUT)
    finally:
        _last_request_at = time.monotonic()
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text


def post_url(post_no):
    """글번호로 원문 주소를 만든다."""
    return f"{config.BASE_URL}?bo_table={config.BO_TABLE}&wr_id={post_no}"


# ---------------------------------------------------------------- 목록


def fetch_list(page=1):
    """목록 페이지 하나를 가져와 글 정보 목록을 돌려준다."""
    html = _get({"bo_table": config.BO_TABLE, "page": page})
    return parse_list(html)


def parse_list(html):
    """목록 페이지 HTML에서 글 정보를 뽑는다.

    돌려주는 값: [{"post_no", "title", "date", "url", "board_category", "pinned"}, ...]
    """
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.select("table tbody tr"):
        link = tr.select_one(".bo_tit a")
        if link is None:  # "게시물이 없습니다" 같은 빈 줄
            continue

        wr_id = parse_qs(urlparse(link["href"]).query).get("wr_id", [None])[0]
        if wr_id is None:
            continue

        cate = tr.select_one(".bo_cate_link")
        date = tr.select_one(".td_datetime")
        rows.append(
            {
                "post_no": int(wr_id),
                "title": link.get_text(" ", strip=True),
                "date": date.get_text(strip=True) if date else "",
                "url": post_url(wr_id),
                "board_category": cate.get_text(strip=True) if cate else "",
                # 상단 고정 공지. 오래된 글이어도 맨 위에 있으므로 새 글 판별 때 따로 다룬다.
                "pinned": "bo_notice" in (tr.get("class") or []),
            }
        )
    return rows


# ---------------------------------------------------------------- 상세


def fetch_detail(post_no):
    """글 상세 페이지를 가져와 본문 정보를 돌려준다."""
    html = _get({"bo_table": config.BO_TABLE, "wr_id": post_no})
    return parse_detail(html)


def parse_detail(html):
    """상세 페이지 HTML에서 본문 정보를 뽑는다.

    돌려주는 값: {"title", "posted_at", "board_category", "content", "images", "attachments"}
    """
    soup = BeautifulSoup(html, "html.parser")

    title = soup.select_one("#bo_v_title .bo_v_tit")
    cate = soup.select_one("#bo_v_title .bo_v_cate")
    date = soup.select_one("#bo_v_title .if_date")
    body = soup.select_one("#bo_v_con")

    images = []
    content = ""
    if body is not None:
        for img in body.select("img"):
            if img.get("src"):
                images.append(img["src"])
        content = _body_to_text(body)

    # 첨부파일 다운로드 주소는 시간이 지나면 만료되므로 파일 이름만 저장한다.
    attachments = [
        a.get_text(strip=True) for a in soup.select("#bo_v_file .view_file_download strong")
    ]

    return {
        "title": title.get_text(" ", strip=True) if title else "",
        "posted_at": _parse_posted_at(date.get_text(" ", strip=True)) if date else "",
        "board_category": cate.get_text(strip=True) if cate else "",
        "content": content,
        "images": images,
        "attachments": attachments,
    }


_BLOCK_TAGS = ["p", "div", "li", "tr", "table", "h1", "h2", "h3", "h4", "h5", "h6"]


def _body_to_text(body):
    """본문 HTML을 줄바꿈이 살아있는 글로 바꾼다.

    신청 링크 같은 주소는 요약에 필요할 수 있으므로 '글자 (주소)' 형태로 남긴다.
    """
    for a in body.select("a[href]"):
        if "view_image" in (a.get("class") or []):  # 이미지 크게 보기 링크는 버린다
            continue
        text = a.get_text(strip=True)
        if text and a["href"] != text:
            a.append(f" ({a['href']})")
    for br in body.find_all("br"):
        br.replace_with("\n")
    for el in body.find_all(_BLOCK_TAGS):
        el.append("\n")
    return _clean_text(body.get_text())


def _clean_text(text):
    """줄마다 앞뒤 공백을 지우고, 빈 줄이 여러 개 이어지면 하나로 줄인다."""
    lines = [line.strip() for line in text.replace("\xa0", " ").splitlines()]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _parse_posted_at(text):
    """'작성일 26-11-13 17:14' 형태를 '2026-11-13 17:14' 로 바꾼다."""
    m = re.search(r"(\d{2})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})", text)
    if not m:
        return ""
    return datetime.strptime(" ".join(m.groups()), "%y %m %d %H %M").strftime("%Y-%m-%d %H:%M")
