import json
from notices_pipeline import (
    CATEGORY_TREE,
    NoticePipelineEngine,
    get_db_connection,
    init_llm_tables,
)

TEST_DB = "test_app.db"


def seed_dummy_data(db_path: str = TEST_DB) -> None:
    """연동 전 테스트용 가짜 공지 & 유저 데이터 삽입"""
    sample_notices = [
        (
            10001,
            "2026학년도 교직 적성 및 인성검사 신청 안내",
            "교직이수 예정자를 대상으로 2026학년도 교직 적성 및 인성검사를 실시합니다. "
            "신청 기간은 2026.11.23 ~ 2026.11.25이며, 학과 사무실에 신청서를 제출하세요.",
            "2026-11-20 10:00",
            "https://aicollege.knu.ac.kr/bbs/board.php?bo_table=sub6_1_a&wr_id=10001",
            "학사",
            json.dumps(["/data/editor/2611/sample_poster.png"]),
            "[]",
        ),
        (
            10002,
            "2026학년도 2학기 교내 학업장려장학금 신청 안내",
            "직전 학기 평점 3.0 이상 학부 재학생을 대상으로 교내장학금을 선발합니다. "
            "2026.11.24 오후 5시까지 온라인 신청 및 성적증명서를 제출해 주세요.",
            "2026-11-20 11:00",
            "https://aicollege.knu.ac.kr/bbs/board.php?bo_table=sub6_1_a&wr_id=10002",
            "장학",
            "[]",
            "[]",
        ),
    ]

    with get_db_connection(db_path) as conn:
        # 테스트용 로그인 유저 (notices_pipeline.py의 users 스키마에 맞춰 notify_email 사용)
        conn.execute(
            """
            INSERT OR IGNORE INTO users
                (username, password_hash, email, phone, notify_email, notify_sms, subscribed_categories)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("test_student", "pbkdf2:sha256:dummy_hash", "test@example.com", "010-0000-0000", 1, 0, "[]"),
        )

        # 테스트용 공지 원문
        conn.executemany(
            """
            INSERT OR IGNORE INTO notices
                (post_no, title, content, date, url, board_category, images, attachments)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            sample_notices,
        )
        conn.commit()


if __name__ == "__main__":
    init_llm_tables(TEST_DB)
    seed_dummy_data(TEST_DB)

    engine = NoticePipelineEngine(db_path=TEST_DB)

    # 1. DB에서 가짜 공지를 읽어 LLM 요약/분류 및 DB 저장
    summarized = engine.run_pipeline_from_db(only_unsummarized=True, send_email=False)
    print("=== 요약 및 분류 결과 ===")
    print(json.dumps(summarized, ensure_ascii=False, indent=2))

    # 2. 대표 카테고리 필터링 및 이미지 URL 확인
    print("\n=== '학사' 필터 조회 ===")
    print(json.dumps(engine.get_notices(main_category="학사"), ensure_ascii=False, indent=2))

    # 3. 확정된 세부 카테고리로 필터 조회 (예: '학사' > '학적' 또는 '교육')
    sample_sub = CATEGORY_TREE["학사"][2]  # "학적"
    print(f"\n=== '학사 > {sample_sub}' 세부 필터 조회 ===")
    print(
        json.dumps(
            engine.get_notices(main_category="학사", sub_category=sample_sub),
            ensure_ascii=False,
            indent=2,
        )
    )

    # 4. RAG 검색 확인
    print("\n=== RAG 검색 테스트 ===")
    answer = engine.rag_search("교직 적성 및 인성검사 언제까지 신청해?")
    print(answer)