# ==============================================================================
# 학과 공지사항 AI 관리 시스템 (LLM 관리 모듈)
# 담당: LLM 관리 팀 (김경민, 전수민)
# ==============================================================================

import json
import os
import re
import smtplib
import sqlite3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import chromadb
import requests
from sentence_transformers import SentenceTransformer

# ==============================================================================
# 1. 환경 설정 및 확정 카테고리 체계
# ==============================================================================
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
DB_PATH = os.getenv("APP_DB_PATH", "app.db")
SITE_BASE_URL = "https://aicollege.knu.ac.kr"

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# 대표 카테고리 -> 세부 카테고리 목록 (각 세부 카테고리는 대표 카테고리 1개에만 소속)
CATEGORY_TREE: Dict[str, List[str]] = {
    "학사": ["수강신청", "졸업", "학적", "교육", "수업"],
    "장학": ["교내장학", "국가장학", "외부장학"],
    "취업·인턴": ["채용", "인턴십", "현장실습", "취업 프로그램"],
    "공모전·대회": ["공모전", "해커톤", "경진대회", "학술대회"],
    "연구": ["학부연구생", "연구실 모집", "연구과제", "논문"],
    "행사·프로그램": ["특강", "세미나", "설명회", "비교과 프로그램"],
    "해외·교류": ["해외연수", "교환학생", "국제교류"],
    "일반": ["학부 소식", "시설 안내", "기타 공지"],
}

DEFAULT_MAIN_CATEGORY = "일반"
DEFAULT_SUB_CATEGORY = "기타 공지"

# ChromaDB 로컬 벡터 스토어 초기화
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="university_notices")

# 임베딩 모델 로드
embedding_model = SentenceTransformer("BAAI/bge-m3")


# ==============================================================================
# 2. DB 연결 및 카테고리/이미지 헬퍼
# ==============================================================================
def get_db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_llm_tables(db_path: str = DB_PATH) -> None:
    """LLM 파이프라인 및 알림 연동에 필요한 최소 테이블 구조 보장"""
    with get_db_connection(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                notify_email INTEGER DEFAULT 1,
                notify_sms INTEGER DEFAULT 0,
                subscribed_categories TEXT DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notices (
                post_no INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                date TEXT,
                url TEXT,
                board_category TEXT,
                images TEXT DEFAULT '[]',
                attachments TEXT DEFAULT '[]',
                main_category TEXT,
                sub_category TEXT,
                summary TEXT,
                target TEXT,
                application_period TEXT,
                documents TEXT DEFAULT '[]',
                is_summarized INTEGER DEFAULT 0,
                is_emailed INTEGER DEFAULT 0
            )
        """)


def _normalize_image_urls(raw_images: Any) -> List[str]:
    """공지 내부 이미지 주소를 웹 페이지에서 바로 표시 가능한 URL 리스트로 변환"""
    if not raw_images:
        return []
    if isinstance(raw_images, str):
        try:
            items = json.loads(raw_images)
        except json.JSONDecodeError:
            items = [raw_images]
    elif isinstance(raw_images, list):
        items = raw_images
    else:
        return []

    urls: List[str] = []
    for src in items:
        if not isinstance(src, str) or not src.strip():
            continue
        src = src.strip()
        if src.startswith(("http://", "https://", "data:")):
            urls.append(src)
        else:
            urls.append(urljoin(SITE_BASE_URL, src))
    return urls


def _normalize_categories(main_cat: str, sub_cat: str) -> Tuple[str, str]:
    """대표 카테고리 1개 + 해당 대표 카테고리의 세부 카테고리 1개로 확정/보정"""
    main_cat = (main_cat or "").strip()
    sub_cat = (sub_cat or "").strip()

    if main_cat not in CATEGORY_TREE:
        for m_key, s_list in CATEGORY_TREE.items():
            if sub_cat in s_list:
                return m_key, sub_cat
        return DEFAULT_MAIN_CATEGORY, DEFAULT_SUB_CATEGORY

    valid_subs = CATEGORY_TREE[main_cat]
    if sub_cat in valid_subs:
        return main_cat, sub_cat

    return main_cat, valid_subs[-1]


# ==============================================================================
# 3. LLM 요약·분류 / RAG / 조회 / 알림 엔진
# ==============================================================================
class NoticePipelineEngine:
    def __init__(
        self,
        db_path: str = DB_PATH,
        ollama_host: str = OLLAMA_HOST,
        model_name: str = MODEL_NAME,
    ):
        self.db_path = db_path
        self.ollama_host = ollama_host
        self.model_name = model_name

    def call_ollama(self, prompt: str, system_prompt: str = "") -> str:
        url = f"{self.ollama_host}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 1024,
            },
        }
        try:
            response = requests.post(url, json=payload, timeout=180)
            response.raise_for_status()
            return response.json().get("response", "")
        except requests.exceptions.Timeout:
            print("[오류] LLM 응답 시간 초과 (Timeout)")
            return "{}"
        except requests.exceptions.RequestException as e:
            print(f"[오류] Ollama 서버 연결 실패: {e}")
            return "{}"

    def process_and_classify_notice(self, notice_title: str, notice_content: str) -> Dict[str, Any]:
        """공지 제목·본문을 분석해 요약 및 확정된 대표/세부 카테고리(각 1개)를 반환"""
        category_guide = "\n".join(
            [f"- {main}: {', '.join(subs)}" for main, subs in CATEGORY_TREE.items()]
        )

        system_prompt = (
            "당신은 대학 학과 공지사항 분석 AI 에이전트입니다.\n"
            "아래 [카테고리 체계]에서 반드시 'main_category' 1개와 해당 대표 카테고리의 'sub_category' 1개만 선택하세요.\n"
            "세부 카테고리는 반드시 선택한 대표 카테고리 목록 안에 있는 항목만 골라야 합니다.\n\n"
            f"[카테고리 체계]\n{category_guide}\n\n"
            "마크다운 백틱(```json) 없이 정확히 아래 JSON 형식으로만 응답하세요:\n"
            "{\n"
            '  "main_category": "대표 카테고리 중 택1",\n'
            '  "sub_category": "선택한 대표 카테고리의 세부 카테고리 중 택1",\n'
            '  "summary": "핵심 내용을 3줄 이내로 요약",\n'
            '  "target": "지원 대상 (예: 전체 재학생, 3~4학년 등)",\n'
            '  "application_period": "신청 기간 (예: 2026.11.23 ~ 2026.11.25 또는 해당없음)",\n'
            '  "documents": ["제출 서류1", "제출 서류2"]\n'
            "}"
        )

        prompt = f"[공지 제목]: {notice_title}\n\n[공지 본문]:\n{notice_content}"
        raw_response = self.call_ollama(prompt, system_prompt)
        cleaned_response = re.sub(r"```json|```", "", raw_response).strip()

        try:
            parsed = json.loads(cleaned_response)
        except json.JSONDecodeError:
            print(f"[경고] JSON 파싱 실패. 원본 응답:\n{raw_response}")
            parsed = {
                "main_category": DEFAULT_MAIN_CATEGORY,
                "sub_category": DEFAULT_SUB_CATEGORY,
                "summary": (notice_content[:120] + "...") if len(notice_content) > 120 else notice_content,
                "target": "전체",
                "application_period": "확인 필요",
                "documents": [],
            }

        main_cat, sub_cat = _normalize_categories(
            parsed.get("main_category", ""),
            parsed.get("sub_category", ""),
        )
        parsed["main_category"] = main_cat
        parsed["sub_category"] = sub_cat
        if not isinstance(parsed.get("documents"), list):
            parsed["documents"] = []
        return parsed

    def chunk_text(self, text: str, chunk_size: int = 300, overlap: int = 50) -> List[str]:
        if not text:
            return [""]
        chunks = []
        for i in range(0, len(text), chunk_size - overlap):
            chunks.append(text[i : i + chunk_size])
        return chunks if chunks else [text]

    def upsert_notice_to_vector_db(
        self,
        notice_id: int,
        title: str,
        content: str,
        main_category: str,
        sub_category: str,
        url: str = "",
    ) -> None:
        chunks = self.chunk_text(content)
        ids, embeddings, documents, metadatas = [], [], [], []

        for idx, chunk in enumerate(chunks):
            chunk_id = f"notice_{notice_id}_chunk_{idx}"
            vector = embedding_model.encode(chunk).tolist()
            ids.append(chunk_id)
            embeddings.append(vector)
            documents.append(chunk)
            metadatas.append(
                {
                    "notice_id": notice_id,
                    "title": title,
                    "main_category": main_category,
                    "sub_category": sub_category,
                    "url": url,
                }
            )

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def run_pipeline_from_db(
        self,
        limit: Optional[int] = None,
        only_unsummarized: bool = True,
        send_email: bool = True,
        send_sms: bool = False,
    ) -> List[Dict[str, Any]]:
        """DB에서 공지를 읽어 LLM 요약·분류 후 저장하고, 요약된 공지 목록을 돌려준다."""
        summarized_notices: List[Dict[str, Any]] = []

        with get_db_connection(self.db_path) as conn:
            sql = """
                SELECT post_no, title, content, date, url, board_category, images, attachments
                FROM notices
            """
            params: List[Any] = []
            if only_unsummarized:
                sql += " WHERE is_summarized = 0 OR summary IS NULL"
            sql += " ORDER BY post_no ASC"
            if limit is not None:
                sql += " LIMIT ?"
                params.append(limit)

            rows = conn.execute(sql, params).fetchall()

            for row in rows:
                post_no = row["post_no"]
                title = row["title"]
                content = row["content"] or ""
                images = _normalize_image_urls(row["images"])

                ai_result = self.process_and_classify_notice(title, content)
                main_cat = ai_result["main_category"]
                sub_cat = ai_result["sub_category"]
                summary = ai_result.get("summary", "")
                target = ai_result.get("target", "전체")
                period = ai_result.get("application_period", "확인 필요")
                documents = ai_result.get("documents", [])

                conn.execute(
                    """
                    UPDATE notices
                    SET main_category = ?,
                        sub_category = ?,
                        summary = ?,
                        target = ?,
                        application_period = ?,
                        documents = ?,
                        images = ?,
                        is_summarized = 1
                    WHERE post_no = ?
                    """,
                    (
                        main_cat,
                        sub_cat,
                        summary,
                        target,
                        period,
                        json.dumps(documents, ensure_ascii=False),
                        json.dumps(images, ensure_ascii=False),
                        post_no,
                    ),
                )

                self.upsert_notice_to_vector_db(
                    notice_id=post_no,
                    title=title,
                    content=content,
                    main_category=main_cat,
                    sub_category=sub_cat,
                    url=row["url"] or "",
                )

                summarized_notices.append(
                    {
                        "post_no": post_no,
                        "title": title,
                        "date": row["date"],
                        "url": row["url"],
                        "main_category": main_cat,
                        "sub_category": sub_cat,
                        "summary": summary,
                        "target": target,
                        "application_period": period,
                        "documents": documents,
                        "images": images,
                    }
                )

            conn.commit()

        if summarized_notices:
            if send_email:
                self.send_email_notifications(summarized_notices)
            if send_sms:
                self.send_sms_notifications(summarized_notices)

        return summarized_notices

    def get_notices(
        self,
        main_category: Optional[str] = None,
        sub_category: Optional[str] = None,
        limit: int = 30,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """대표 카테고리(main_category) 또는 세부 카테고리(sub_category)별로 공지 목록 필터링 조회"""
        conditions = ["is_summarized = 1"]
        params: List[Any] = []

        if main_category and main_category != "전체":
            conditions.append("main_category = ?")
            params.append(main_category)

        if sub_category and sub_category != "전체":
            conditions.append("sub_category = ?")
            params.append(sub_category)

        where_clause = " WHERE " + " AND ".join(conditions)
        sql = f"""
            SELECT post_no, title, date, url, main_category, sub_category,
                   summary, target, application_period, documents, images
            FROM notices
            {where_clause}
            ORDER BY post_no DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        with get_db_connection(self.db_path) as conn:
            rows = conn.execute(sql, params).fetchall()

        return [
            {
                "post_no": r["post_no"],
                "title": r["title"],
                "date": r["date"],
                "url": r["url"],
                "main_category": r["main_category"],
                "sub_category": r["sub_category"],
                "summary": r["summary"],
                "target": r["target"],
                "application_period": r["application_period"],
                "documents": json.loads(r["documents"] or "[]"),
                "images": _normalize_image_urls(r["images"]),
            }
            for r in rows
        ]

    def send_email_notifications(self, new_notices: List[Dict[str, Any]]) -> int:
        """이메일을 등록한 유저에게 새 요약 공지 이메일 발송"""
        if not SMTP_USER or not SMTP_PASSWORD:
            print("[안내] SMTP_USER / SMTP_PASSWORD 미설정으로 이메일 발송을 건너뜁니다.")
            return 0

        with get_db_connection(self.db_path) as conn:
            users = conn.execute(
                """
                SELECT id, username, email, subscribed_categories
                FROM users
                WHERE email IS NOT NULL AND TRIM(email) != '' AND COALESCE(notify_email, 1) = 1
                """
            ).fetchall()

        if not users:
            return 0

        sent_count = 0
        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)

                for user in users:
                    subs = json.loads(user["subscribed_categories"] or "[]")
                    matched = [
                        n
                        for n in new_notices
                        if not subs
                        or n["main_category"] in subs
                        or n["sub_category"] in subs
                    ]
                    if not matched:
                        continue

                    msg = MIMEMultipart("alternative")
                    msg["Subject"] = f"[학과 공지 알림] 새 공지사항 {len(matched)}건"
                    msg["From"] = SMTP_USER
                    msg["To"] = user["email"]

                    items_html = []
                    for n in matched:
                        img_html = (
                            f'<p><img src="{n["images"][0]}" style="max-width:480px;border-radius:6px;"></p>'
                            if n["images"]
                            else ""
                        )
                        items_html.append(
                            f"""
                            <div style="border:1px solid #ddd;padding:12px;margin-bottom:12px;border-radius:8px;">
                              <strong>[{n['main_category']} &gt; {n['sub_category']}]</strong>
                              <h3 style="margin:6px 0;">{n['title']}</h3>
                              <p>{n['summary']}</p>
                              <p>대상: {n['target']} | 기간: {n['application_period']}</p>
                              {img_html}
                              <a href="{n['url']}">원문 보기</a>
                            </div>
                            """
                        )

                    body = f"<html><body><p>{user['username']}님, 새 공지 요약입니다.</p>{''.join(items_html)}</body></html>"
                    msg.attach(MIMEText(body, "html", "utf-8"))
                    server.sendmail(SMTP_USER, user["email"], msg.as_string())
                    sent_count += 1

            with get_db_connection(self.db_path) as conn:
                conn.executemany(
                    "UPDATE notices SET is_emailed = 1 WHERE post_no = ?",
                    [(n["post_no"],) for n in new_notices],
                )
                conn.commit()
        except Exception as e:
            print(f"[오류] 이메일 발송 실패: {e}")

        return sent_count

    def send_sms_notifications(self, new_notices: List[Dict[str, Any]]) -> int:
        """문자(SMS) 발송 연동용 자리 (외부 SMS API 키 확정 시 구현)"""
        print(f"[안내] SMS 발송 대기 ({len(new_notices)}건) - SMS API 연동 후 활성화")
        return 0

    def rag_search(
        self,
        query: str,
        top_k: int = 3,
        main_category: Optional[str] = None,
        sub_category: Optional[str] = None,
    ) -> str:
        query_vector = embedding_model.encode(query).tolist()
        where_filter: Optional[Dict[str, Any]] = None
        if main_category and sub_category:
            where_filter = {"$and": [{"main_category": main_category}, {"sub_category": sub_category}]}
        elif main_category:
            where_filter = {"main_category": main_category}
        elif sub_category:
            where_filter = {"sub_category": sub_category}

        results = collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where=where_filter,
        )

        retrieved_docs = results.get("documents", [[]])[0]
        retrieved_metas = results.get("metadatas", [[]])[0]
        if not retrieved_docs:
            return "관련된 공지사항을 찾을 수 없습니다."

        context_str = "\n".join(
            [
                f"- [출처: {meta.get('title')} ({meta.get('main_category')} > {meta.get('sub_category')})] {doc}"
                for doc, meta in zip(retrieved_docs, retrieved_metas)
            ]
        )
        system_prompt = (
            "당신은 대학 학과 공지사항 안내 챗봇입니다. "
            "제공된 참고 문서(Context)를 바탕으로 사용자의 질문에 정확하고 친절하게 답변하세요."
        )
        prompt = f"[참고 문서]:\n{context_str}\n\n[사용자 질문]: {query}"
        return self.call_ollama(prompt, system_prompt)