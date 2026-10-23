# 🎓 Smart University Knowledge Hub — Dong-A University RAG Chatbot

Интеллектуальный помощник для поиска информации в официальных документах **Dong-A University**.

Проект построен на архитектуре **RAG (Retrieval-Augmented Generation)**. Система ищет релевантную информацию только в загруженных официальных документах университета и использует найденный контекст для генерации ответа.

Основная цель проекта — уменьшить количество галлюцинаций LLM и предоставить студентам удобный способ поиска информации о поступлении, академических правилах и академическом календаре.

---

## 🚀 Возможности

- ответы на вопросы на основе официальных документов Dong-A University;
- поддержка английского, корейского и русского языков;
- автоматическое определение категории вопроса;
- гибридный поиск: semantic search + BM25;
- фильтрация документов по типу студента и уровню обучения;
- сохранение метаданных источников;
- отображение источников ответа;
- fallback-ответ, если информации в базе знаний недостаточно;
- логирование запросов для дальнейшей оценки системы;
- тестирование retrieval-качества;
- запуск через Streamlit;
- контейнеризация с Docker и Docker Compose.

---

## 📚 База знаний

На данный момент система использует три основных типа официальной информации Dong-A University.

### 1. Поступление иностранных студентов

Документ:

```text
2027_spring_international_student_undergraduate_admission.pdf
```

Содержит информацию о:

- доступных направлениях обучения;
- сроках подачи документов;
- необходимых документах;
- языковых требованиях;
- стоимости обучения;
- application fee;
- стипендиях;
- общежитии;
- требованиях для иностранных абитуриентов.

Категория:

```text
applicant
```

---

### 2. Академические правила

Документ:

```text
2026_donga_academics.pdf
```

Содержит информацию о:

- регистрации на предметы;
- повторном прохождении предметов;
- оценках и GPA;
- академическом отпуске;
- возвращении после академического отпуска;
- academic warning;
- требованиях к выпуску;
- признании кредитов.

Категория:

```text
academic_policy
```

---

### 3. Академический календарь

Источник — официальный академический календарь Dong-A University.

Обработанная версия:

```text
md/2026_donga_academic_calendar.md
```

Содержит информацию о:

- начале семестров;
- периодах регистрации;
- промежуточных экзаменах;
- финальных экзаменах;
- праздничных днях;
- других академических датах.

Категория:

```text
academic_calendar
```

---

## 🧠 Архитектура RAG

Общий процесс работы системы:

```text
Official Dong-A University Documents
                │
                ▼
        PDF / Web Extraction
                │
                ▼
           Markdown
                │
                ▼
            Chunking
                │
                ▼
      Multilingual Embeddings
                │
                ▼
             Chroma
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
          Top-K Context
                │
                ▼
              Groq
                │
                ▼
     Context-based Answer
                │
                ▼
            Streamlit
```

---

## 🔎 Поиск информации

Для retrieval используется гибридный подход.

### Semantic Search

Для создания multilingual embeddings используется:

```text
intfloat/multilingual-e5-base
```

Модель позволяет искать информацию между несколькими языками.

Например, пользователь может задать вопрос на английском или русском языке, даже если исходный документ написан на корейском языке.

### BM25

BM25 используется для keyword-based поиска.

Это особенно полезно для:

- названий документов;
- дат;
- терминов;
- названий департаментов;
- конкретных академических понятий.

### Hybrid Search

Результаты semantic search и BM25 объединяются с помощью **Reciprocal Rank Fusion (RRF)**.

После объединения выбираются наиболее релевантные chunks для передачи LLM.

---

## 🗂 Автоматическое определение категории

Перед retrieval система анализирует вопрос пользователя и определяет наиболее подходящую категорию:

```text
applicant
academic_policy
academic_calendar
all
```

Например:

```text
What scholarships are available?
```

→ `applicant`

```text
Can I retake a course?
```

→ `academic_policy`

```text
When are the final exams?
```

→ `academic_calendar`

Если категория не может быть определена надежно, поиск выполняется по всей базе знаний.

---

## 🌍 Мультиязычность

Система поддерживает:

- 🇬🇧 English
- 🇰🇷 한국어
- 🇷🇺 Русский

Для retrieval используется multilingual embedding model.

Система также формирует поисковый запрос с учетом нескольких языков, чтобы повысить вероятность нахождения информации в документах, написанных на другом языке.

Ответ формируется на языке вопроса пользователя.

---

## 🛡 Защита от галлюцинаций

LLM получает строгую инструкцию использовать **только найденный контекст**.

Система не должна придумывать:

- даты;
- суммы;
- требования к поступлению;
- языковые баллы;
- стипендии;
- названия департаментов;
- академические правила;
- другую информацию, отсутствующую в базе знаний.

Если информации недостаточно, используется fallback-ответ.

Это позволяет уменьшить вероятность генерации неподтвержденной информации.

---

## 🛠 Технологии

Проект использует:

```text
Python 3.11
Streamlit
ChromaDB
Sentence Transformers
intfloat/multilingual-e5-base
BM25
Groq API
PyMuPDF
BeautifulSoup
Docker
Docker Compose
```

LLM по умолчанию:

```text
openai/gpt-oss-20b
```

---

## 📁 Структура проекта

```text
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
│
├── data/
│   └── donga/
│       ├── 2026_donga_academics.pdf
│       └── 2027_spring_international_student_undergraduate_admission.pdf
│
├── md/
│   ├── 2026_donga_academics.md
│   ├── 2026_donga_academic_calendar.md
│   └── 2027_spring_international_student_undergraduate_admission.md
│
├── chroma_db/
│
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
```

---

# 🐳 Запуск через Docker

## 1. Клонировать репозиторий

```bash
git clone git@github.com:asel6320/donga_rag_chatbot.git
cd donga_rag_chatbot
```

---

## 2. Создать `.env`

Создайте файл:

```text
.env
```

На основе:

```text
.env.example
```

Добавьте Groq API key:

```env
GROQ_API_KEY=YOUR_GROQ_API_KEY
LLM_MODEL=openai/gpt-oss-20b
```

Файл `.env` находится в `.gitignore` и не должен загружаться в GitHub.

---

## 3. Запустить Docker

```bash
docker compose up --build
```

После запуска приложение будет доступно по адресу:

```text
http://localhost:8501
```

При первом запуске загрузка embedding-модели может занять некоторое время.

---

## 4. Остановить приложение

Нажмите:

```text
Ctrl + C
```

Затем:

```bash
docker compose down
```

---

# 💻 Локальный запуск

## 1. Создать виртуальное окружение

```bash
python3.11 -m venv smart-university-hub
```

Активировать:

### macOS / Linux

```bash
source smart-university-hub/bin/activate
```

---

## 2. Установить зависимости

```bash
pip install -r requirements.txt
```

---

## 3. Настроить `.env`

```env
GROQ_API_KEY=YOUR_GROQ_API_KEY
LLM_MODEL=openai/gpt-oss-20b
```

---

## 4. Запустить Streamlit

```bash
streamlit run app.py
```

Открыть:

```text
http://localhost:8501
```

---

# 🧩 Подготовка документов

Pipeline обработки документов состоит из нескольких этапов.

### PDF → Markdown

```bash
python extract_pdf.py
```

Для академического календаря используется:

```bash
python extract_calendar.py
```

После extraction документы сохраняются в папке:

```text
md/
```

---

### Markdown → Chunks

```bash
python chunk.py
```

Chunks сохраняются в:

```text
chunks.json
```

Каждый chunk содержит metadata, например:

```text
source
category
page
section
level
student_type
intake
content_type
```

---

## 📊 Текущая база chunks

В текущей версии базы знаний:

```text
Admissions:        55 chunks
Academic policy:   84 chunks
Academic calendar:  4 chunks
--------------------------------
Total:            143 chunks
```

Из них таблицы также сохраняются как отдельный тип контента для более точного retrieval.

---

# 🧪 Evaluation

Для проверки качества retrieval используется:

```text
evaluate.py
test_set.json
```

Тестовый набор включает вопросы по:

- admissions;
- academic policy;
- academic calendar;
- multilingual retrieval;
- вопросам, для которых информация отсутствует.

Полученные результаты retrieval evaluation:

```text
Hit@5: 29 / 31
Hit@5 accuracy: ~94%
MRR: 0.841
Keyword recall: ~87%
```

Эти метрики используются для проверки того, насколько часто правильный контекст попадает в Top-5 результатов поиска.

---

# 💬 Примеры вопросов

### Admissions

```text
What is the application fee?
What documents do I need?
What departments can international students apply to?
What scholarships are available for freshmen?
What are the English language requirements?
```

### Academic Policy

```text
Can I retake a course?
What is the academic warning criterion?
Can I extend my academic leave?
What happens if I do not return after academic leave?
```

### Academic Calendar

```text
When does the first semester start?
When is course registration?
When are the midterm exams?
When are the final exams?
```

### Русский

```text
Когда заканчивается регистрация?
Какие документы нужны для поступления?
Какие есть стипендии?
Когда начинаются финальные экзамены?
```

### 한국어

```text
수강신청 기간은 언제인가요?
재수강이 가능한가요?
1학기 기말고사는 언제인가요?
외국인 신입생 장학금이 있나요?
```

---

# ⚠️ Ограничения

Система отвечает только на основе документов, находящихся в текущей базе знаний.

Если необходимой информации нет в загруженных официальных документах, система должна сообщить об отсутствии информации, а не использовать внешние знания.

Качество ответа зависит от:

- качества extraction исходного документа;
- структуры Markdown;
- chunking;
- retrieval;
- полноты базы знаний.

Некоторые короткие или неоднозначные follow-up вопросы могут требовать дополнительного контекста.

---

# 🎯 Цель проекта

Цель Smart University Knowledge Hub — показать, как RAG может использоваться для создания надежного университетского AI-помощника, который:

- работает с официальными документами;
- поддерживает несколько языков;
- предоставляет проверяемые ответы;
- снижает количество hallucinations;
- может расширяться новыми университетскими документами без изменения основной архитектуры.
