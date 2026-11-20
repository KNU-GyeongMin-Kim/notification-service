# 서버 (server)

크롤러, 데이터베이스, LLM, 화면을 잇는 Flask API 서버입니다.

- 담당: 김문수
- 브랜치: `feature/backend`

## 하는 일

1. 10분마다 크롤러를 실행해 새 공지를 DB에 저장합니다. 서버를 켜자마자 한 번 바로 실행합니다.
   DB가 비어 있으면 첫 수집으로 최근 365일 글(약 500건, 약 1시간 30분)을 가져옵니다.
2. 화면(React)이 공지 목록과 상세를 가져갈 수 있게 JSON API를 제공합니다.
3. (2주차 예정) 새 공지를 LLM으로 요약하고, 키워드가 맞는 사용자에게 이메일을 보냅니다.

첫 수집(기간 수집)한 글은 "기존 공지"로 저장해서 알림 대상에서 뺍니다. 새 글 수집이라도 작성된 지 3일이 넘은 글은 알림을 보내지 않습니다.

첫 수집이 중간에 멈췄다면(서버 종료 등) `python -m server --backfill 365`로 남은 글을 마저 가져옵니다. 이미 있는 글은 건너뜁니다.

## 실행 방법

저장소 최상위 폴더에서 실행합니다.

```
pip install -r requirements.txt
python -m server                 # API 서버 + 10분마다 자동 수집
python -m server --no-scheduler  # API 서버만 (자동 수집 끔, 화면 작업할 때)
python -m server --crawl-once    # 수집 한 번만 하고 끝냄
python -m server --backfill 365  # 최근 365일 글을 모두 수집하고 끝냄 (이미 있는 글은 건너뜀)
```

- 주소: http://127.0.0.1:5000
- DB 파일: 저장소 최상위의 `notices.db` (저장소에는 올라가지 않음)
- 사이트 규칙에 따라 요청 사이에 10초씩 쉬므로 글 1건에 약 10초 걸립니다. 첫 수집 기간은 `config.py`의 `FIRST_RUN_DAYS`로 바꿀 수 있습니다. 개발 중에는 `python -m server --backfill 7`로 짧게 채워두는 걸 추천합니다.

## 파일 구성

| 파일 | 내용 |
|---|---|
| `__main__.py` | 실행 진입점, 자동 수집 예약 |
| `app.py` | API 주소와 응답 형식 |
| `jobs.py` | 주기 작업 (수집, 이후 요약·알림) |
| `config.py` | 포트, DB 위치, 수집 주기 등 설정 |

## API

모든 응답은 JSON입니다. 공지 번호(`id`)는 게시판 글번호(`post_no`)를 그대로 씁니다.

| 주소 | 내용 |
|---|---|
| `GET /api/health` | 서버 상태, 저장된 공지 수, 마지막 수집 결과 |
| `GET /api/notices` | 공지 목록 (최신순) |
| `GET /api/notices/<id>` | 공지 상세 (본문, 이미지, 첨부파일 포함) |
| `GET /api/categories` | 분류별 공지 개수 |

### 공지 목록

`GET /api/notices?page=1&size=20&category=장학`

| 값 | 내용 | 기본값 |
|---|---|---|
| `page` | 페이지 번호 | 1 |
| `size` | 한 페이지 개수 (최대 100) | 20 |
| `category` | 분류. 비우거나 `전체`면 모두 | 없음 |

```json
{
  "items": [
    {
      "id": 29526,
      "title": "[융합전공] 2027학년도 1학기 융합전공 이수 대상자 선발 안내",
      "date": "2026-11-19 10:38",
      "url": "https://aicollege.knu.ac.kr/bbs/board.php?bo_table=sub6_1_a&wr_id=29526",
      "category": "일반공지",
      "board_category": "일반공지",
      "summary": null,
      "target": null,
      "apply_period": null,
      "has_attachments": true
    }
  ],
  "total": 15,
  "page": 1,
  "size": 20
}
```

- `category`: AI 분류가 있으면 AI 분류, 없으면 게시판 분류입니다.
- `summary`, `target`, `apply_period`: LLM 요약이 붙기 전에는 `null`입니다.

### 공지 상세

`GET /api/notices/29526` — 목록 항목에 아래가 더해집니다. 없는 번호면 404입니다.

| 항목 | 내용 |
|---|---|
| `content` | 본문 글 |
| `images` | 본문 이미지 주소 목록 |
| `attachments` | 첨부파일 이름 목록 (파일은 원문 링크에서 받기) |
| `documents` | 제출 서류 목록 (LLM) |
| `fetched_at` | 수집 시각 |

### 화면에서 호출하기

React 개발 서버(`http://localhost:5173`)에서 오는 요청은 허용되어 있습니다.

```js
const res = await fetch("http://127.0.0.1:5000/api/notices?page=1");
const data = await res.json();
```

## 진행 상황

- [x] Flask 서버 뼈대, 공지 목록·상세·분류 API
- [x] 10분마다 자동 수집, 첫 수집은 최근 365일 기간 수집, 알림 제외
- [ ] 새 공지 LLM 요약 연결 (2주차)
- [ ] 사용자·키워드 API (로그인 방식 결정 후)
- [ ] 키워드 맞는 사용자에게 이메일 발송 (2주차)
- [ ] 시연용 공지 직접 넣기 기능
