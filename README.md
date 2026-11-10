🎓 Smart University Knowledge Hub — Dong-A University RAG Chatbot

프로젝트 소개

Smart University Knowledge Hub는 동아대학교(Dong-A University)의 공식 문서를 기반으로 학생들에게 정확한 학사 및 입학 정보를 제공하는 AI 챗봇입니다.

본 프로젝트는 RAG(Retrieval-Augmented Generation, 검색 증강 생성) 아키텍처를 활용합니다. 사용자의 질문과 관련된 정보를 공식 문서에서 검색하고, 검색된 내용을 바탕으로 답변을 생성합니다.

프로젝트의 주요 목표는 LLM의 환각(Hallucination) 현상을 최소화하고, 학생들이 입학 요강, 학사 규정 및 학사 일정에 관한 정보를 쉽고 빠르게 확인할 수 있도록 지원하는 것입니다.

🚀 주요 기능

동아대학교 공식 문서 기반 질의응답

한국어, 영어, 러시아어 지원

질문 유형 자동 분류

Semantic Search와 BM25를 결합한 하이브리드 검색

학생 유형 및 학위 과정에 따른 문서 필터링

문서 출처 및 메타데이터 관리

답변에 사용된 출처 표시

정보가 부족한 경우 대체 응답(Fallback) 제공

사용자 질문 및 검색 결과 로깅

검색 성능 평가(Evaluation)

Streamlit 기반 웹 인터페이스

Docker 및 Docker Compose를 이용한 실행 환경 구성

📚 지식 베이스(Knowledge Base)

현재 시스템은 동아대학교의 공식 자료를 세 가지 유형으로 분류하여 활용합니다.

1. 외국인 유학생 입학 안내

문서: 2027_spring_international_student_undergraduate_admission.pdf

주요 내용:

지원 가능한 학과 및 전공

원서 접수 일정

제출 서류

어학 능력 요건

등록금 및 전형료

장학금

기숙사

외국인 지원 자격

카테고리: applicant

2. 학사 규정

문서: 2026_donga_academics.pdf

주요 내용:

수강신청

재수강

성적 및 GPA

휴학 및 복학

학사경고

졸업 요건

학점 인정

카테고리: academic_policy

3. 학사 일정

출처: 동아대학교 공식 학사 일정 웹페이지

변환 파일: md/2026_donga_academic_calendar.md

주요 내용:

학기 시작일

수강신청 기간

중간고사 및 기말고사

공휴일

기타 주요 학사 일정

카테고리: academic_calendar

🧠 RAG 시스템 아키텍처

시스템의 전체 처리 과정은 다음과 같습니다.

동아대학교 공식 문서 (PDF / Web)
                │
                ▼
           문서 추출
                │
                ▼
         Markdown 변환
                │
                ▼
         Chunking 처리
                │
                ▼
      Multilingual Embeddings
                │
                ▼
             ChromaDB
                │
        ┌───────┴───────┐
        ▼               ▼
 Semantic Search      BM25
        │               │
        └───────┬───────┘
                ▼
      Hybrid Search / RRF
                │
                ▼
        Top-K 검색 결과
                │
                ▼
            Groq LLM
                │
                ▼
        문서 기반 답변 생성
                │
                ▼
           Streamlit

🔎 검색 시스템

Semantic Search

다국어 의미 기반 검색을 위해 다음 임베딩 모델을 사용합니다.

intfloat/multilingual-e5-base

이 모델은 서로 다른 언어로 작성된 질문과 문서 사이의 의미적 유사성을 계산합니다.

예를 들어 사용자가 영어로 질문하더라도 한국어로 작성된 학사 규정에서 관련 정보를 검색할 수 있습니다.

BM25

BM25는 키워드 기반 검색 알고리즘입니다.

문서명, 날짜, 학과명 및 특정 학사 용어와 같은 정확한 키워드를 검색하는 데 활용됩니다.

Hybrid Search

Semantic Search와 BM25의 검색 결과를 Reciprocal Rank Fusion(RRF) 방식으로 결합합니다.

이후 관련성이 높은 상위 문서 청크(Top-K)를 선택하여 LLM에 전달합니다.

🗂 질문 카테고리 자동 분류

시스템은 사용자 질문을 분석하여 다음 카테고리 중 하나로 분류합니다.

applicant
academic_policy
academic_calendar
all

분류 예시

사용자 질문

카테고리

What scholarships are available?

applicant

Can I retake a course?

academic_policy

When are the final exams?

academic_calendar

질문의 카테고리가 불명확한 경우 전체 지식 베이스를 대상으로 검색합니다.

🌍 다국어 지원

시스템은 다음 세 가지 언어를 지원합니다.

한국어

영어

러시아어

다국어 임베딩 모델과 검색어 확장을 활용하여 질문 언어와 문서 언어가 다른 경우에도 관련 정보를 검색하도록 설계되었습니다.

최종 답변은 사용자가 질문한 언어로 생성됩니다.

🛡 환각(Hallucination) 최소화

LLM에는 검색된 문서의 내용만을 활용하도록 제한하는 시스템 프롬프트가 적용됩니다.

시스템은 문서에서 확인되지 않은 날짜, 금액, 입학 요건, 장학금, 학과 및 학사 규정을 임의로 생성하지 않도록 설계되었습니다.

충분한 근거가 없는 경우에는 정보가 부족하다는 대체 응답을 제공합니다.

🛠 기술 스택

구분

기술

프로그래밍 언어

Python 3.11

웹 인터페이스

Streamlit

벡터 데이터베이스

ChromaDB

임베딩

Sentence Transformers

임베딩 모델

intfloat/multilingual-e5-base

키워드 검색

BM25

하이브리드 검색

Reciprocal Rank Fusion

LLM

Groq API

기본 LLM 모델

openai/gpt-oss-20b

PDF 처리

PyMuPDF

웹 문서 처리

BeautifulSoup

컨테이너

Docker, Docker Compose

📁 프로젝트 구조

smart-university-hub/
│
├── app.py
├── answer.py
├── index_search.py
├── chunk.py
│
├── extract_pdf.py
├── extract_calendar.py
│
├── evaluate.py
├── rag_logger.py
├── test_set.json
│
├── chunks.json
├── data/
├── md/
├── chroma_db/
├── logs/
│
├── requirements.txt
├── .env.example
├── .gitignore
│
├── Dockerfile
├── docker-compose.yml
│
└── README.md

주요 파일 설명

파일

기능

app.py

Streamlit 웹 인터페이스

answer.py

질문 분석 및 LLM 답변 생성

index_search.py

ChromaDB 및 하이브리드 검색

chunk.py

문서 청크 생성

extract_pdf.py

PDF 문서 추출

extract_calendar.py

학사 일정 웹페이지 추출

evaluate.py

검색 성능 평가

rag_logger.py

실행 로그 관리

test_set.json

평가용 질문 데이터

chunks.json

처리된 문서 청크

🐳 Docker 실행 방법

1. GitHub 저장소 복제

git clone git@github.com:asel6320/donga_rag_chatbot.git
cd donga_rag_chatbot

2. 환경 변수 설정

프로젝트 루트에 .env 파일을 생성하고 다음 내용을 입력합니다.

GROQ_API_KEY=YOUR_GROQ_API_KEY
LLM_MODEL=openai/gpt-oss-20b

실제 API Key는 GitHub에 업로드하지 않습니다.

3. Docker 실행

docker compose up --build

실행 후 브라우저에서 다음 주소로 접속합니다.

http://localhost:8501

최초 실행 시 Hugging Face에서 임베딩 모델을 다운로드하므로 시간이 다소 소요될 수 있습니다.

4. Docker 종료

터미널에서 Ctrl + C를 누른 후 다음 명령어를 실행합니다.

docker compose down

💻 로컬 실행 방법

1. 가상환경 생성

python3.11 -m venv .venv

macOS / Linux:

source .venv/bin/activate

Windows:

.venv\Scripts\activate

2. 라이브러리 설치

pip install -r requirements.txt

3. 환경 변수 설정

.env 파일에 Groq API Key와 모델명을 입력합니다.

GROQ_API_KEY=YOUR_GROQ_API_KEY
LLM_MODEL=openai/gpt-oss-20b

4. Streamlit 실행

streamlit run app.py

접속 주소: http://localhost:8501

🧩 문서 처리 파이프라인

PDF 및 웹페이지 추출

python extract_pdf.py
python extract_calendar.py

추출한 문서는 Markdown 형식으로 저장됩니다.

문서 청크 생성

python chunk.py

생성된 청크는 chunks.json에 저장됩니다.

각 청크에는 다음과 같은 메타데이터가 포함됩니다.

source
category
page
section
level
student_type
intake
content_type

현재 데이터 구성

문서 유형

청크 수

입학 안내

55

학사 규정

84

학사 일정

4

전체

143

표 형식의 데이터도 별도로 처리하여 검색에 활용합니다.

🧪 성능 평가(Evaluation)

시스템의 검색 성능을 확인하기 위해 evaluate.py와 test_set.json을 사용합니다.

평가 데이터에는 입학 안내, 학사 규정, 학사 일정 및 다국어 질문이 포함됩니다.

Retrieval 평가 결과

평가 지표

결과

Hit@5

29 / 31

Hit@5 Accuracy

약 94%

MRR

0.841

Keyword Recall

약 87%

Hit@5는 정답과 관련된 문서가 상위 5개 검색 결과에 포함되는 비율을 의미합니다.

MRR(Mean Reciprocal Rank)은 정답 문서가 검색 결과에서 얼마나 높은 순위에 위치하는지 평가하는 지표입니다.

💬 질문 예시

입학 안내

What is the application fee?
What documents do I need?
What departments can international students apply to?
What scholarships are available for freshmen?

학사 규정

Can I retake a course?
What is the academic warning criterion?
Can I extend my academic leave?

학사 일정

When does the first semester start?
When is course registration?
When are the final exams?

한국어

수강신청 기간은 언제인가요?
재수강이 가능한가요?
1학기 기말고사는 언제인가요?
외국인 신입생 장학금이 있나요?

러시아어

Какие документы нужны для поступления?
Какие есть стипендии?
Когда начинаются финальные экзамены?

⚠️ 시스템의 한계

현재 시스템은 지식 베이스에 등록된 공식 문서만을 기반으로 답변합니다.

따라서 등록되지 않은 학년도나 최신 공지사항에 대한 정보는 제공하지 못할 수 있습니다.

또한 검색 및 답변 품질은 문서 추출, Markdown 구조, 청크 분할 및 검색 정확도에 영향을 받습니다.

현재 대화 기록은 화면에 표시되지만, 이전 대화 내용을 이용한 후속 질문 해석 기능은 완전히 구현되지 않았습니다.

🔐 보안

Groq API Key는 .env 파일을 통해 관리합니다.

.env는 .gitignore에 등록되어 GitHub에 업로드되지 않으며, .env.example에는 실제 API Key를 포함하지 않습니다.

🎯 프로젝트 목표

Smart University Knowledge Hub는 공식 대학 문서와 RAG 기술을 결합하여 신뢰할 수 있는 다국어 대학 정보 안내 시스템을 구축하는 것을 목표로 합니다.

이를 통해 학생들은 입학 및 학사 정보를 자연어로 검색하고, 관련 출처를 확인하며, 필요한 정보를 보다 효율적으로 얻을 수 있습니다.

향후 추가 공식 문서를 지식 베이스에 통합하여 서비스 범위를 확장할 수 있습니다.
