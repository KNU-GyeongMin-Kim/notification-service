# ==============================================================================
# 학과 공지사항 AI 관리 시스템 (notices.json 연동 버전)
# 담당: LLM 관리 팀 (김경민, 전수민)
# ==============================================================================

import json
import re
from typing import Dict, List, Any
import requests
import chromadb
from sentence_transformers import SentenceTransformer

# 1. 설정 및 초기화
OLLAMA_HOST = "http://localhost:11434"
MODEL_NAME = "qwen2.5:7b"  # 사용 중인 Ollama 모델명

# ChromaDB 로컬 벡터 스토어 초기화
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="university_notices")

# 임베딩 모델 로드 (한국어 지원 경량형 모델)
embedding_model = SentenceTransformer("BAAI/bge-m3")


class NoticePipelineEngine:
    
    def __init__(self, ollama_host: str = OLLAMA_HOST, model_name: str = MODEL_NAME):
        self.ollama_host = ollama_host
        self.model_name = model_name

    def call_ollama(self, prompt: str, system_prompt: str = "") -> str:
        """Ollama API 호출 함수 (타임아웃 및 예외 처리 포함)"""
        url = f"{self.ollama_host}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # JSON 및 분류 정확도를 위해 낮게 설정
                "num_predict": 1024
            }
        }
        
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            return response.json().get("response", "")
        except requests.exceptions.Timeout:
            print("[오류] LLM 응답 시간 초과 (Timeout)")
            return "{}"
        except requests.exceptions.RequestException as e:
            print(f"[오류] Ollama 서버 연결 실패: {e}")
            return "{}"

    # --------------------------------------------------------------------------
    # 2. 공지사항 가공 및 자동 분류 (JSON 추출)
    # --------------------------------------------------------------------------
    def process_and_classify_notice(self, notice_title: str, notice_content: str) -> Dict[str, Any]:
        system_prompt = (
            "당신은 대학 학과 공지사항 분석 AI 에이전트입니다. "
            "주어진 공지사항을 분석하여 정확히 아래의 JSON 포맷으로만 응답하세요. 마크다운 백틱(```json)을 쓰지 말고 순수 JSON 문자열만 출력하세요.\n"
            "{\n"
            '  "category": "학사" 또는 "장학" 또는 "취업" 또는 "행사" 또는 "일반공지 중 택1",\n'
            '  "summary": "핵심 내용을 3줄 이내로 요약",\n'
            '  "target": "지원 대상 (예: 전체 재학생, 교직이수자 등)",\n'
            '  "application_period": "신청 기간 (예: 2026.11.17 ~ 2026.11.19 또는 해당없음)",\n'
            '  "documents": ["제출 서류1", "제출 서류2"]\n'
            "}"
        )
        
        prompt = f"[공지 제목]: {notice_title}\n\n[공지 본문]:\n{notice_content}"
        raw_response = self.call_ollama(prompt, system_prompt)
        cleaned_response = re.sub(r"```json|```", "", raw_response).strip()
        
        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            print(f"[경고] JSON 파싱 실패. 원본 응답:\n{raw_response}")
            return {
                "category": "일반공지",
                "summary": notice_content[:100] + "...",
                "target": "전체",
                "application_period": "확인 필요",
                "documents": []
            }

    # --------------------------------------------------------------------------
    # 3. RAG 파이프라인 (Chunking & Vector DB 적재)
    # --------------------------------------------------------------------------
    def chunk_text(self, text: str, chunk_size: int = 300, overlap: int = 50) -> List[str]:
        chunks = []
        for i in range(0, len(text), chunk_size - overlap):
            chunks.append(text[i:i + chunk_size])
        return chunks if chunks else [text]

    def add_notice_to_vector_db(self, notice_id: int, title: str, content: str, category: str):
        chunks = self.chunk_text(content)
        ids, embeddings, documents, metadatas = [], [], [], []
        
        for idx, chunk in enumerate(chunks):
            chunk_id = f"notice_{notice_id}_chunk_{idx}"
            vector = embedding_model.encode(chunk).tolist()
            
            ids.append(chunk_id)
            embeddings.append(vector)
            documents.append(chunk)
            metadatas.append({
                "notice_id": notice_id,
                "title": title,
                "category": category
            })
            
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        print(f"[Vector DB] 공지 No.{notice_id} ({title}) - {len(chunks)}개 청크 적재 완료")

    # --------------------------------------------------------------------------
    # 4. RAG 자연어 검색
    # --------------------------------------------------------------------------
    def rag_search(self, query: str, top_k: int = 3) -> str:
        query_vector = embedding_model.encode(query).tolist()
        results = collection.query(query_embeddings=[query_vector], n_results=top_k)
        
        retrieved_docs = results.get("documents", [[]])[0]
        retrieved_metas = results.get("metadatas", [[]])[0]
        
        if not retrieved_docs:
            return "관련된 공지사항을 찾을 수 없습니다."
            
        context_texts = []
        for doc, meta in zip(retrieved_docs, retrieved_metas):
            context_texts.append(f"- [출처: {meta.get('title')} (분류: {meta.get('category')})] {doc}")
            
        context_str = "\n".join(context_texts)
        system_prompt = (
            "당신은 대학 학과 공지사항 안내 챗봇입니다. "
            "제공된 참고 문서(Context)를 바탕으로 사용자의 질문에 정확하고 친절하게 답변하세요."
        )
        prompt = f"[참고 문서]:\n{context_str}\n\n[사용자 질문]: {query}"
        
        return self.call_ollama(prompt, system_prompt)


# ==============================================================================
# 메인 실행: notices.json 파일 읽어서 자동 처리
# ==============================================================================
if __name__ == "__main__":
    engine = NoticePipelineEngine()
    
    # 1. notices.json 파일 로드
    with open("notices.json", "r", encoding="utf-8") as f:
        notices_data = json.load(f)
    
    print(f"=== 총 {len(notices_data)}건의 공지사항 처리 시작 ===")
    
    processed_results = []
    for notice in notices_data:
        post_no = notice["post_no"]
        title = notice["title"]
        content = notice["content"]
        original_category = notice["board_category"]
        
        print(f"\n[처리 중] No.{post_no} - {title}")
        
        # A. LLM 가공 및 JSON 추출
        ai_result = engine.process_and_classify_notice(title, content)
        print(" > AI 분석 결과:", json.dumps(ai_result, ensure_ascii=False))
        
        # B. Vector DB 적재
        engine.add_notice_to_vector_db(
            notice_id=post_no,
            title=title,
            content=content,
            category=ai_result.get("category", original_category)
        )
        
        processed_results.append({
            "post_no": post_no,
            "title": title,
            "ai_analysis": ai_result
        })
        
    print("\n=== 모든 공지사항 적재 및 가공 완료 ===")
    
    # 2. RAG 검색 테스트 (교직 검사 관련 질문)
    print("\n--- [RAG 검색 테스트] ---")
    query = "교직 적성 및 인성검사 언제 신청해야 돼?"
    print(f"질문: {query}")
    answer = engine.rag_search(query)
    print(f"답변:\n{answer}")