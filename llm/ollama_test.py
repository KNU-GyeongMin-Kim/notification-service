import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:9b")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
CATEGORIES = ["학사", "장학", "취업·인턴", "공모전·대회", "연구", "행사·프로그램", "해외·교류", "일반"]


def summarize_and_classify(notice):
    prompt = f"""다음 대학 공지의 핵심을 한국어로 요약하고 분류.

분류는 다음 중 하나만 선택해라: {", ".join(CATEGORIES)}

분류 기준:
- 학사: 수강신청, 졸업, 학적, 교육, 수업
- 장학: 교내장학, 국가장학, 외부장학
- 취업·인턴: 채용, 인턴십, 현장실습, 취업 프로그램
- 공모전·대회: 공모전, 해커톤, 경진대회, 학술대회
- 연구: 학부연구생, 연구실 모집, 연구과제, 논문
- 행사·프로그램: 특강, 세미나, 설명회, 비교과 프로그램
- 해외·교류: 해외연수, 교환학생, 국제교류
- 일반: 학부 소식, 시설 안내, 기타 공지

국내 대학 사이의 학점교류나 국내 대학 수강 신청은 학사로 분류하세요. 해외연수, 해외 대학 파견, 국제교류에 해당할 때만 해외·교류로 분류하세요.
융합전공, 복수전공, 전공 이수자 선발은 학사로 분류하세요. 공모전·경진대회·학술대회는 행사 성격도 있더라도 공모전·대회를 우선하세요. 본문이 비어 있으면 제목과 게시판 분류를 근거로 분류하세요.

요약은 본문에 있는 사실만 사용하고, 일정이나 대상이 중요하면 포함하세요. 본문은 최대 두 문장으로 요약하세요. 제목과 게시판 분류도 참고하되, 본문 내용을 우선하세요. 숫자와 한국어 단위는 붙여 써서 2차, 12월, 4인처럼 자연스러운 표기로 작성하세요.

다음 JSON 객체만 반환하세요. summary는 문자열, category는 지정된 분류 중 하나여야 합니다.
{{"summary":"...","category":"..."}}

공지:
제목: {notice.get("title", "")}
게시판 분류: {notice.get("board_category", "")}
본문: {notice.get("content", "")}
첨부파일: {", ".join(notice.get("attachments", []))}
"""
    payload = json.dumps(
        {
            "model": MODEL,
            "stream": False,
            "think": False,
            "format": "json",
            "options": {"temperature": 0, "num_predict": 180},
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode("utf-8")
    request = Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=600) as response:
        result = json.loads(response.read().decode("utf-8"))
    generated = json.loads(result["message"]["content"])
    if not isinstance(generated.get("summary"), str) or generated.get("category") not in CATEGORIES:
        raise ValueError(f"모델 응답 형식 또는 분류가 올바르지 않습니다: {generated}")
    generated["summary"] = re.sub(r"(?<=\d)\s+(?=(?:년|월|일|시|분|차|인|학기|회|명|시간|주|개월|호관|호|층|학점|학년|만원|만|억|점))", "", generated["summary"])
    return generated


def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("test.json")
    with input_path.open(encoding="utf-8") as file:
        notices = json.load(file)
    if not isinstance(notices, list):
        raise ValueError("입력 JSON은 공지 객체를 담은 배열이어야 합니다.")
    output = []
    total_started = time.perf_counter()
    inference_times = []
    for notice in notices:
        started = time.perf_counter()
        generated = summarize_and_classify(notice)
        elapsed = time.perf_counter() - started
        inference_times.append(elapsed)
        print(f"post_no={notice.get('post_no')} 추론 시간: {elapsed:.2f}초", file=sys.stderr)
        output.append(
            {
                "post_no": notice.get("post_no"),
                "title": notice.get("title", ""),
                "summary": generated["summary"],
                "category": generated["category"],
            }
        )
    print(json.dumps(output, ensure_ascii=False, indent=2))
    total_elapsed = time.perf_counter() - total_started
    average_elapsed = sum(inference_times) / len(inference_times) if inference_times else 0
    print(f"공지 {len(notices)}건 추론 합계: {sum(inference_times):.2f}초", file=sys.stderr)
    print(f"공지 1건 평균 추론 시간: {average_elapsed:.2f}초", file=sys.stderr)
    print(f"전체 실행 시간: {total_elapsed:.2f}초", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        print(f"Ollama 요청 실패 ({error.code}): {detail}", file=sys.stderr)
        sys.exit(1)
    except URLError as error:
        print(f"Ollama에 연결할 수 없습니다: {error.reason}", file=sys.stderr)
        print("Ollama를 실행하고 모델이 설치되어 있는지 확인하세요.", file=sys.stderr)
        sys.exit(1)
