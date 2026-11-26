import argparse
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

주요 공지 목적을 하나 골라 분류하세요. 제목에 보조 키워드가 있더라도 실제 모집·신청·변경 내용이 중심인 항목을 우선하세요.

우선 적용 규칙:
- 정규 교과목, 계절수업, 수강·학점교류, 졸업·학적, 자격 요건, 필수 안전교육은 학사입니다.
- 설명회·세미나·특강 참석자를 모집하는 공지는 행사·프로그램입니다. 단, 공무원·기업 채용시험이나 취업 선발 절차를 안내하는 설명회는 취업·인턴입니다.
- 공모전·해커톤·경진대회 참가팀이나 참가자를 모집하면 공모전·대회입니다. 관련 교육이나 설명회가 함께 있어도 대회 참가 모집이 중심이면 공모전·대회입니다.
- 채용, 취업 과정, 인턴십, 현장실습은 취업·인턴입니다. 해외 현장에서 진행되는 인턴십도 취업·인턴입니다.
- 해외·교류는 학생의 해외연수, 해외 대학 교류·파견, 국제 봉사·교류 프로그램에만 사용하세요. 기업의 해외진출 지원 사업은 일반입니다.
- 연구실·연구 참여자 모집이나 연구과제 지원은 연구입니다. 기업과 대학 연구진이 공동 연구개발을 수행하는 과제도 연구입니다.
- 정규 수업이 아닌 자격증 교육, 도서관 이용 교육, 비교과 캠프·프로그램은 행사·프로그램입니다.
- 융합전공·복수전공 이수자 선발은 학사입니다. 해당 전공 설명회 참석자 모집은 행사·프로그램입니다.
- 본문이 비어 있으면 제목과 게시판 분류를 근거로 판단하세요.

예시:
- 국내 대학 겨울계절수업 학점교류 신청 → 학사
- 융합전공 설명회 참석자 모집 → 행사·프로그램
- 지역인재 7급 시험 변경 안내 또는 시험 대비 설명회 → 취업·인턴
- 연구실 안전교육 미이수자 이수 안내 → 학사
- AI 경진대회 참가팀 모집 → 공모전·대회
- 태국 진출을 준비하는 기업 대상 지원사업 → 일반

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
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?", default=str(Path(__file__).with_name("test.json")))
    parser.add_argument("--out")
    args = parser.parse_args()
    input_path = Path(args.input)
    with input_path.open(encoding="utf-8") as file:
        notices = json.load(file)
    if not isinstance(notices, list):
        raise ValueError("입력 JSON은 공지 객체를 담은 배열이어야 합니다.")
    output = []
    output_path = Path(args.out) if args.out else None
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
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(output, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    output_json = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    if not args.out:
        print(output_json, end="")
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
