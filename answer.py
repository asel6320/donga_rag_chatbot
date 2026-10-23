import argparse
import os
import re
import time
from pathlib import Path

from groq import Groq

import index_search as ix
import rag_logger


# ============================================================
# ENV
# ============================================================

_DOTENV = {}


def _load_dotenv(path: Path):
    """
    Small .env reader.
    Existing environment variables take priority.
    """

    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        if line.startswith("export "):
            line = line[len("export "):]

        key, value = line.split("=", 1)

        key = key.strip()
        value = value.strip()

        # Allow:
        # KEY=value # comment
        if value[:1] not in ('"', "'") and " #" in value:
            value = value.split(" #", 1)[0].strip()

        value = value.strip("\"'")

        _DOTENV[key] = value

        # Terminal environment variable wins over .env
        os.environ.setdefault(key, value)


# Always look for .env next to answer.py
_load_dotenv(Path(__file__).resolve().parent / ".env")


# ============================================================
# CONFIG
# ============================================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# You can override this by adding LLM_MODEL=... to .env
LLM_MODEL = os.environ.get(
    "LLM_MODEL",
    "openai/gpt-oss-20b",
)

TOP_K = 5

# Increase after evaluating retrieval quality.
MIN_SCORE = 0.0


# Internal signal used by the LLM.
FALLBACK = "NO_INFORMATION"


def get_fallback(question: str) -> str:
    """
    Return the fallback message in the language of the question.
    """

    # Korean
    if re.search(r"[가-힣]", question):
        return (
            "죄송하지만 이 질문에 대한 정확한 정보가 없습니다. "
            "학생지원실(101호)에 문의해 주세요."
        )

    # Russian
    if re.search(r"[А-Яа-яЁё]", question):
        return (
            "К сожалению, у меня нет точной информации по этому вопросу. "
            "Пожалуйста, обратитесь в Студенческий офис (кабинет 101)."
        )

    # English / default
    return (
        "Unfortunately, I don't have exact information about this question. "
        "Please contact the Student Office (Room 101)."
    )


SYSTEM_PROMPT = """
You are an assistant for university applicants and students.

Answer ONLY using the numbered context passages provided by the user.

Rules:

1. Never use outside knowledge.

2. Never guess or invent:
   - dates
   - amounts
   - admission requirements
   - scores
   - scholarships
   - departments
   - professors
   - employment statistics
   - university rules

3. If the context does not contain enough information to answer the
   question, reply with exactly:

NO_INFORMATION

4. Detect the language of the user's QUESTION and write the final answer
   entirely in that same language.

   - English question -> answer only in English.
   - Russian question -> answer only in Russian.
   - Korean question -> answer only in Korean.

   The language of the retrieved context does NOT determine the answer
   language. If the context is in a different language from the question,
   translate the relevant information into the language of the question.

5. Quote numbers, dates, deadlines, fees and percentages exactly as
   written in the context.

6. If the context says that information is "subject to change",
   semester-specific, year-specific, or applies only to a particular
   intake, mention that limitation.

7. After every factual statement, add the relevant passage number,
   for example [1] or [2].

8. Do not cite a passage that does not support the statement.

9. Be concise.
""".strip()


# ============================================================
# GROQ
# ============================================================

_client = None


def get_client():
    """
    Create Groq client using GROQ_API_KEY from .env.
    """

    global _client

    if _client is None:

        if not GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY is not set. "
                "Add GROQ_API_KEY=gsk_... to the .env file next to answer.py."
            )

        _client = Groq(
            api_key=GROQ_API_KEY,
            timeout=60,
        )

    return _client


def call_llm(messages: list[dict]) -> str:
    """
    Send messages to the model through Groq.
    """

    response = get_client().chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=0,
    )

    return (response.choices[0].message.content or "").strip()


# ============================================================
# MULTILINGUAL QUERY EXPANSION
# ============================================================

VALID_CATEGORIES = {
    "applicant",
    "academic_policy",
    "academic_calendar",
    "all",
}


def analyze_search_query(question: str) -> tuple[str, str | None]:
    """
    Expand the question for multilingual retrieval and automatically
    choose the most relevant document category.

    If the question is unclear or mixed, no category filter is used.
    """

    messages = [
        {
            "role": "system",
            "content": (
                "You prepare retrieval queries for a university RAG system. "
                "Do NOT answer the user's question. "
                "Choose exactly one category: applicant, academic_policy, "
                "academic_calendar, or all. "
                "Use applicant for admissions, departments/programs, applications, "
                "required documents, application fees, tuition, scholarships, "
                "dormitory information, language requirements, and admission schedules. "
                "Use academic_policy for rules for enrolled students, including "
                "course registration rules, retakes, grades, GPA, leave/return, "
                "academic warnings, graduation, and credit recognition. "
                "Use academic_calendar when the main purpose is to find an academic "
                "calendar date such as semester start/end, course registration dates, "
                "exam periods, or holidays. "
                "Use all when the question is unclear, very short, mixed, or uncertain. "
                "Then produce short equivalent search terms in Korean, English, and "
                "Russian. Preserve years, numbers, semesters, department names, and "
                "proper nouns exactly. "
                "Return exactly two lines:\n"
                "CATEGORY: <category>\n"
                "QUERY: <multilingual search terms>"
            ),
        },
        {
            "role": "user",
            "content": question,
        },
    ]

    try:
        analysis = call_llm(messages)

        category_match = re.search(
            r"(?im)^CATEGORY:\s*(applicant|academic_policy|academic_calendar|all)\s*$",
            analysis,
        )
        query_match = re.search(r"(?im)^QUERY:\s*(.+)$", analysis)

        detected = category_match.group(1).lower() if category_match else "all"

        if detected not in VALID_CATEGORIES:
            detected = "all"

        expansion = query_match.group(1).strip() if query_match else analysis.strip()

        search_query = question
        if expansion:
            search_query = f"{question}\n{expansion}"

        category_filter = None if detected == "all" else detected
        return search_query, category_filter

    except Exception:
        # Analysis failure must not stop retrieval.
        return question, None


def expand_search_query(question: str) -> str:
    """
    Backwards-compatible helper for older code/tests.
    """
    search_query, _ = analyze_search_query(question)
    return search_query


# ============================================================
# GROQ DIAGNOSTICS
# ============================================================

def list_models() -> list[str]:
    """
    Return model IDs available through the Groq API.
    """

    models = get_client().models.list()

    return sorted(model.id for model in models.data)


def check_key() -> None:
    """
    Check GROQ_API_KEY without displaying the full key.
    """

    key = os.environ.get("GROQ_API_KEY", "")

    if not key:
        print(
            "GROQ_API_KEY not found.\n"
            "Add this to .env next to answer.py:\n\n"
            "GROQ_API_KEY=gsk_..."
        )
        return

    if len(key) > 8:
        masked = f"{key[:4]}...{key[-2:]}"
    else:
        masked = "(very short!)"

    print(f"key found: {masked}   length: {len(key)}")

    from_file = _DOTENV.get("GROQ_API_KEY")

    if from_file is None:
        print(
            "source: terminal environment variable "
            "(no GROQ_API_KEY line found in .env)"
        )

    elif from_file != key:
        print(
            "WARNING: GROQ_API_KEY from the terminal overrides "
            "the value in .env.\n"
            "If the terminal key is old, run:\n"
            "unset GROQ_API_KEY"
        )

    else:
        print("source: .env file")

    if any(c.isspace() for c in key):
        print("WARNING: API key contains whitespace.")

    if not key.startswith("gsk_"):
        print(
            "WARNING: This does not look like a Groq API key. "
            "Groq keys normally start with gsk_."
        )

    try:

        ids = list_models()

        print("OK: Groq accepted the API key.")

        print("\nAvailable models:")

        for model_id in ids:
            print(f"  {model_id}")

        print(f"\nCurrent model: {LLM_MODEL}")

        if LLM_MODEL not in ids:
            print(
                "\nWARNING: Your configured LLM_MODEL was not found "
                "in the available model list."
            )

    except Exception as e:
        print(f"REJECTED by Groq: {type(e).__name__}: {e}")


# ============================================================
# RAG CONTEXT
# ============================================================

def build_context(hits: list[dict]) -> str:
    """
    Convert retrieved chunks into numbered context passages.
    """

    blocks = []

    for i, h in enumerate(hits, start=1):

        m = h["metadata"]

        source = m.get("source", "Unknown source")
        section = m.get("section", "Unknown section")
        page_number = m.get("page_number", "?")

        blocks.append(
            f"[{i}] "
            f"({source}, {section}, page {page_number})\n"
            f"{h['text']}"
        )

    return "\n\n".join(blocks)


def sources_from(hits: list[dict]) -> list[dict]:
    """
    Convert retrieved chunks into source information for Streamlit.
    """

    sources = []

    for i, h in enumerate(hits, start=1):

        metadata = h["metadata"]

        sources.append(
            {
                "n": i,
                "source": metadata.get("source", "Unknown source"),
                "section": metadata.get("section", "Unknown section"),
                "page_number": metadata.get("page_number"),
                "printed_page": metadata.get("printed_page"),
                "file": metadata.get("file"),
                "url": metadata.get("url"),
                "snippet": h["text"].split("\n", 1)[-1][:400],
                "score": h["score"],
            }
        )

    return sources


# ============================================================
# ANSWER
# ============================================================

def answer(
    question: str,
    level=None,
    student_type=None,
    category=None,
) -> dict:

    t0 = time.perf_counter()

    event = {
        "question": question,
        "level": level,
        "student_type": student_type,
        "category": category,
        "llm_provider": "groq",
        "llm_model": LLM_MODEL,
        "min_score": MIN_SCORE,
    }

    hits = []
    llm_ms = None

    try:

        # ----------------------------------------------------
        # QUERY ANALYSIS + MULTILINGUAL EXPANSION
        # ----------------------------------------------------

        search_query, auto_category = analyze_search_query(question)

        # Explicit category from CLI/evaluation has priority.
        # Otherwise use the automatically detected category.
        retrieval_category = category or auto_category

        event["auto_category"] = auto_category or "all"
        event["retrieval_category"] = retrieval_category or "all"

        # ----------------------------------------------------
        # RETRIEVAL
        # ----------------------------------------------------

        hits = ix.hybrid_search(
            search_query,
            top_k=TOP_K,
            min_score=MIN_SCORE,
            level=level,
            student_type=student_type,
            category=retrieval_category,
        )

        retrieval_ms = round(
            (time.perf_counter() - t0) * 1000
        )

        # ----------------------------------------------------
        # GUARDRAIL 1
        # No relevant documents -> don't call answer LLM
        # ----------------------------------------------------

        if not hits:

            result = {
                "answer": get_fallback(question),
                "sources": [],
            }

            outcome = "fallback_no_hits"

        else:

            # ------------------------------------------------
            # CLOUD LLM
            # ------------------------------------------------

            t1 = time.perf_counter()

            # Mask personal information before sending
            # the question to the cloud API.
            safe_question = rag_logger.mask_pii(question)

            messages = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": (
                        f"Context:\n"
                        f"{build_context(hits)}\n\n"
                        f"Question:\n"
                        f"{safe_question}"
                    ),
                },
            ]

            text = call_llm(messages)

            llm_ms = round(
                (time.perf_counter() - t1) * 1000
            )

            # ------------------------------------------------
            # GUARDRAIL 2
            # Model says documents don't contain answer
            # ------------------------------------------------

            if FALLBACK in text:

                result = {
                    "answer": get_fallback(question),
                    "sources": [],
                }

                outcome = "fallback_model"

            else:

                # --------------------------------------------
                # Show only citations actually used
                # --------------------------------------------

                all_sources = sources_from(hits)

                cited = {
                    int(n)
                    for n in re.findall(r"\[(\d+)\]", text)
                }

                shown = [
                    source
                    for source in all_sources
                    if source["n"] in cited
                ]

                # If model forgot citation numbers,
                # show retrieved sources rather than nothing.
                if not shown:
                    shown = all_sources

                result = {
                    "answer": text,
                    "sources": shown,
                }

                outcome = "answered"

        # ----------------------------------------------------
        # RAGAS evaluation
        # ----------------------------------------------------

        result["contexts"] = [
            h["text"]
            for h in hits
        ]

        # ----------------------------------------------------
        # LOGGING
        # ----------------------------------------------------

        event.update(
            outcome=outcome,
            answer=result["answer"],
            retrieval_ms=retrieval_ms,
            llm_ms=llm_ms,
            cited=[
                source["n"]
                for source in result["sources"]
            ],
        )

        return result

    except Exception as e:

        event.update(
            outcome="error",
            error=f"{type(e).__name__}: {e}",
        )

        raise

    finally:

        event["retrieved"] = [
            {
                "n": i,
                "id": h.get("id"),
                "section": h["metadata"].get("section"),
                "page": h["metadata"].get("page_number"),
                "score": h["score"],
            }
            for i, h in enumerate(hits, start=1)
        ]

        event["total_ms"] = round(
            (time.perf_counter() - t0) * 1000
        )

        rag_logger.log_event(event)


# ============================================================
# TERMINAL OUTPUT
# ============================================================

def format_result(res: dict) -> str:

    out = [res["answer"]]

    if res["sources"]:

        out.append("\nSources:")

        for s in res["sources"]:

            printed = (
                f", printed p.{s['printed_page']}"
                if s.get("printed_page")
                else ""
            )

            page = s.get("page_number", "?")

            out.append(
                f"  [{s['n']}] "
                f"{s['source']} - {s['section']} "
                f"(PDF p.{page}{printed})"
            )

    return "\n".join(out)


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":

    ap = argparse.ArgumentParser()

    ap.add_argument(
        "question",
        nargs="?",
    )

    ap.add_argument(
        "--level",
    )

    ap.add_argument(
        "--type",
        dest="student_type",
    )

    ap.add_argument(
        "--category",
    )

    ap.add_argument(
        "--list-models",
        action="store_true",
        help="list Groq models available to your API key",
    )

    ap.add_argument(
        "--check-key",
        action="store_true",
        help="test GROQ_API_KEY without displaying the full key",
    )

    args = ap.parse_args()

    if args.check_key:

        check_key()

    elif args.list_models:

        print("\n".join(list_models()))

    elif args.question:

        print(
            format_result(
                answer(
                    args.question,
                    args.level,
                    args.student_type,
                    args.category,
                )
            )
        )

    else:

        ap.error(
            "give a question, --check-key, or --list-models"
        )