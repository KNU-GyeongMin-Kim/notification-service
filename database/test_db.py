import db

db.DB_PATH = "test.db"  # 테스트용 별도 DB (실제 DB에 영향 없음)
db.init_db()

samples = [
    {"post_no": 29517, "title": "대학문화소식지 박미자 제작 안내", "date": "2026-11-12 09:14",
     "url": "https://aicollege.knu.ac.kr/bbs/board.php?bo_table=sub6_1_a&wr_id=29517",
     "content": "...", "board_category": "일반공지", "images": [], "attachments": [],
     "collected_at": "2026-11-14 14:46:11"},
    {"post_no": 29518, "title": "교직 적성 및 인성검사(3차) 시행 안내", "date": "2026-11-12 10:10",
     "url": "https://aicollege.knu.ac.kr/bbs/board.php?bo_table=sub6_1_a&wr_id=29518",
     "content": "...", "board_category": "학사", "images": [], "attachments": ["안내.pdf"],
     "collected_at": "2026-11-14 14:46:22"},
]

for s in samples:
    print(s["post_no"], "저장됨" if db.add_notice(s, is_initial=True) else "이미 있음")

print("두 번째 시도:", db.add_notice(samples[0]))  # False가 나와야 한다
print("전체 개수:", len(db.get_notices()))