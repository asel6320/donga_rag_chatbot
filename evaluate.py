import argparse
import json
from pathlib import Path

import index_search as ix


LEVEL = "undergraduate"
STUDENT_TYPE = "international"
TOP_K = 5


# ============================================================
# RETRIEVAL EVALUATION
# ============================================================

def retrieval_eval(tests, search=ix.hybrid_search):
    rows = []

    for t in tests:

        if t["id"].startswith(("P", "C")):
            level = None
            student_type = None
        else:
            level = LEVEL
            student_type = STUDENT_TYPE

        hits = search(
            t["question"],
            top_k=TOP_K,
            level=level,
            student_type=student_type,
        )

        pages = [
            h["metadata"]["page_number"]
            for h in hits
        ]

        top_score = (
            hits[0]["score"]
            if hits
            else 0.0
        )

        # ----------------------------------------------------
        # Negative / out-of-scope test
        # ----------------------------------------------------

        if t.get("should_refuse"):

            rows.append(
                {
                    "id": t["id"],
                    "refuse": True,
                    "top_score": top_score,
                }
            )

            continue

        # ----------------------------------------------------
        # Expected page
        # ----------------------------------------------------

        expected = set(t["expected_pages"])

        rank = next(
            (
                i + 1
                for i, p in enumerate(pages)
                if p in expected
            ),
            None,
        )

        # ----------------------------------------------------
        # Keyword recall inside retrieved chunks
        # ----------------------------------------------------

        blob = " ".join(
            h["text"]
            for h in hits
        ).lower()

        found = [
            kw
            for kw in t["keywords"]
            if kw.lower() in blob
        ]

        rows.append(
            {
                "id": t["id"],
                "refuse": False,
                "question": t["question"],
                "hit": rank is not None,
                "rank": rank,
                "kw_recall": (
                    len(found) / len(t["keywords"])
                    if t["keywords"]
                    else 1.0
                ),
                "top_score": top_score,
            }
        )

    return rows


# ============================================================
# PRINT RETRIEVAL RESULTS
# ============================================================

def print_retrieval(rows):

    pos = [
        r
        for r in rows
        if not r["refuse"]
    ]

    neg = [
        r
        for r in rows
        if r["refuse"]
    ]

    print(
        f"\n"
        f"{'id':<5}"
        f"{'hit':<5}"
        f"{'rank':<6}"
        f"{'kw':<6}"
        f"{'top':<7}"
        f"question"
    )

    for r in pos:

        print(
            f"{r['id']:<5}"
            f"{'yes' if r['hit'] else 'NO':<5}"
            f"{str(r['rank'] or '-'):<6}"
            f"{r['kw_recall']:<6.2f}"
            f"{r['top_score']:<7}"
            f"{r['question'][:55]}"
        )

    n = len(pos)

    if n:

        hit_count = sum(
            r["hit"]
            for r in pos
        )

        mrr = sum(
            1 / r["rank"]
            for r in pos
            if r["rank"]
        ) / n

        keyword_recall = sum(
            r["kw_recall"]
            for r in pos
        ) / n

        print(
            f"\nHit@{TOP_K}: "
            f"{hit_count}/{n} = "
            f"{hit_count / n:.0%}"
        )

        print(
            f"MRR: {mrr:.3f}"
        )

        print(
            f"Keyword recall: "
            f"{keyword_recall:.0%}"
        )

        pos_scores = sorted(
            r["top_score"]
            for r in pos
        )

        print(
            "\nTop score on answerable questions: "
            f"min {pos_scores[0]}, "
            f"median {pos_scores[len(pos_scores) // 2]}"
        )

    neg_scores = [
        r["top_score"]
        for r in neg
    ]

    print(
        "Top score on out-of-scope questions: "
        f"{neg_scores}"
    )

    print(
        "-> pick MIN_SCORE (in answer.py) between these "
        "two groups, if they separate."
    )


# ============================================================
# FULL ANSWER EVALUATION
# ============================================================

def answer_eval(tests):

    import answer as rag
    import rag_logger

    # Keep evaluation questions out of real usage logs.
    rag_logger.LOG_ENABLED = False

    ok = 0
    total = 0

    print("\n--- full answers ---")

    for t in tests:

        res = rag.answer(
            t["question"],
            level=LEVEL,
            student_type=STUDENT_TYPE,
        )

        text = res["answer"]

        # ----------------------------------------------------
        # Detect the multilingual user-facing fallback.
        #
        # answer.py uses NO_INFORMATION internally, but the
        # final response is converted into English, Russian,
        # or Korean by get_fallback().
        # ----------------------------------------------------

        refused = (
            text.strip()
            == rag.get_fallback(t["question"]).strip()
        )

        # ----------------------------------------------------
        # Negative question
        # ----------------------------------------------------

        if t.get("should_refuse"):

            passed = refused

        # ----------------------------------------------------
        # Answerable question
        # ----------------------------------------------------

        else:

            kws = t.get(
                "answer_keywords",
                [],
            )

            passed = (
                not refused
                and all(
                    k.lower() in text.lower()
                    for k in kws
                )
            )

        total += 1
        ok += passed

        print(
            f"{'PASS' if passed else 'FAIL'} "
            f"{t['id']}: "
            f"{text[:110]!r}"
        )

    print(
        f"\nAnswer checks passed: "
        f"{ok}/{total}"
    )

    print(
        "Note: keyword checks are strict. "
        "A FAIL may just be different wording - read it."
    )


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":

    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--answers",
        action="store_true",
    )

    ap.add_argument(
        "--tests",
        default="test_set.json",
    )

    ap.add_argument(
        "--vector-only",
        action="store_true",
        help="compare with plain vector search",
    )

    a = ap.parse_args()

    tests = json.loads(
        Path(a.tests).read_text(
            encoding="utf-8"
        )
    )

    search_fn = (
        ix.search
        if a.vector_only
        else ix.hybrid_search
    )

    print(
        "Mode:",
        (
            "vector only"
            if a.vector_only
            else "hybrid (vector + BM25)"
        ),
    )

    print_retrieval(
        retrieval_eval(
            tests,
            search=search_fn,
        )
    )

    if a.answers:

        answer_eval(tests)