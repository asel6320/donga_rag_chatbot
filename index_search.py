import argparse
import json
import re
from pathlib import Path

import chromadb
import numpy as np
from rank_bm25 import BM25Okapi


CHUNKS_FILE = "chunks.json"
DB_PATH = "chroma_db"
COLLECTION = "university"

# Multilingual embedding model.
# E5 models need:
#   "passage: " for documents
#   "query: " for questions
MODEL_NAME = "intfloat/multilingual-e5-base"

_model = None


# ============================================================
# EMBEDDINGS
# ============================================================

def get_model():
    global _model

    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME)

    return _model


def embed_passages(texts: list[str]) -> list[list[float]]:
    return get_model().encode(
        ["passage: " + t for t in texts],
        normalize_embeddings=True,
        show_progress_bar=True,
    ).tolist()


def embed_query(text: str) -> list[float]:
    return get_model().encode(
        ["query: " + text],
        normalize_embeddings=True,
    ).tolist()


# ============================================================
# CHROMA
# ============================================================

def clean_metadata(meta: dict) -> dict:
    """
    Chroma accepts only str / int / float / bool.
    Drop None values and avoid nesting.
    """

    return {
        k: v
        for k, v in meta.items()
        if v is not None
    }


def get_collection():
    client = chromadb.PersistentClient(
        path=DB_PATH
    )

    # Cosine distance:
    # similarity = 1 - distance
    return client.get_or_create_collection(
        COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def build_index(
    chunks_file: str = CHUNKS_FILE,
    embed=embed_passages,
):
    chunks = json.loads(
        Path(chunks_file).read_text(
            encoding="utf-8"
        )
    )

    col = get_collection()

    # Upsert:
    # re-running replaces chunks with the same ID
    # instead of duplicating them.
    col.upsert(
        ids=[
            c["id"]
            for c in chunks
        ],
        documents=[
            c["text"]
            for c in chunks
        ],
        embeddings=embed(
            [
                c["text"]
                for c in chunks
            ]
        ),
        metadatas=[
            clean_metadata(c["metadata"])
            for c in chunks
        ],
    )

    _bm25_cache.clear()

    print(
        f"Indexed {col.count()} chunks "
        f"in '{DB_PATH}'"
    )


# ============================================================
# METADATA FILTER
# ============================================================

def build_filter(
    level=None,
    student_type=None,
    category=None,
    intake=None,
):
    """
    Build the Chroma metadata filter.

    level and student_type support documents marked "all".

    Example:
        User selects:
            level = undergraduate

        Matching documents:
            level = undergraduate
            OR
            level = all

    This allows general academic-policy and calendar documents
    to remain searchable for every student group.
    """

    conds = []

    # --------------------------------------------------------
    # PROGRAM LEVEL
    # --------------------------------------------------------

    if level:
        conds.append(
            {
                "$or": [
                    {"level": level},
                    {"level": "all"},
                ]
            }
        )

    # --------------------------------------------------------
    # STUDENT TYPE
    # --------------------------------------------------------

    if student_type:
        conds.append(
            {
                "$or": [
                    {"student_type": student_type},
                    {"student_type": "all"},
                ]
            }
        )

    # --------------------------------------------------------
    # CATEGORY
    #
    # Category stays exact.
    # If category="academic_calendar", we should not also
    # return unrelated categories.
    # --------------------------------------------------------

    if category:
        conds.append(
            {"category": category}
        )

    # --------------------------------------------------------
    # INTAKE
    #
    # Intake can also contain "all" for general documents.
    # --------------------------------------------------------

    if intake:
        conds.append(
            {
                "$or": [
                    {"intake": intake},
                    {"intake": "all"},
                ]
            }
        )

    if not conds:
        return None

    if len(conds) == 1:
        return conds[0]

    return {
        "$and": conds
    }


# ============================================================
# VECTOR SEARCH
# ============================================================

def search(
    query: str,
    top_k: int = 5,
    min_score: float = 0.0,
    embed=embed_query,
    **filters,
) -> list[dict]:

    col = get_collection()

    res = col.query(
        query_embeddings=embed(query),
        n_results=top_k,
        where=build_filter(**filters),
    )

    hits = []

    for cid, doc, meta, dist in zip(
        res["ids"][0],
        res["documents"][0],
        res["metadatas"][0],
        res["distances"][0],
    ):

        score = 1 - dist

        # Score threshold
        if score >= min_score:

            hits.append(
                {
                    "id": cid,
                    "text": doc,
                    "metadata": meta,
                    "score": round(score, 3),
                }
            )

    return hits


# ============================================================
# HYBRID SEARCH
# ============================================================

_bm25_cache = {}


def tokenize(text: str) -> list[str]:
    return re.findall(
        r"\w+",
        text.lower(),
    )


def get_bm25(where):
    """
    BM25 index over the chunks that match
    the metadata filter.

    Cached so it does not have to be rebuilt
    for every query.
    """

    key = json.dumps(
        where,
        sort_keys=True,
    )

    if key not in _bm25_cache:

        data = get_collection().get(
            where=where,
            include=[
                "documents",
                "metadatas",
            ],
        )

        if data["ids"]:

            bm25 = BM25Okapi(
                [
                    tokenize(d)
                    for d in data["documents"]
                ]
            )

        else:
            bm25 = None

        _bm25_cache[key] = (
            bm25,
            data["ids"],
            data["documents"],
            data["metadatas"],
        )

    return _bm25_cache[key]


def hybrid_search(
    query: str,
    top_k: int = 5,
    min_score: float = 0.0,
    candidate_k: int = 20,
    rrf_k: int = 60,
    bm25_weight: float = 1.0,
    embed=embed_query,
    **filters,
) -> list[dict]:
    """
    Semantic vector search + BM25 keyword search.

    The two rankings are merged using
    Reciprocal Rank Fusion (RRF).

    bm25_weight > 1 gives more importance
    to exact keyword matches.

    Returned "score" is cosine similarity,
    so MIN_SCORE has the same meaning as
    vector-only search.
    """

    where = build_filter(**filters)

    col = get_collection()

    bm25, ids, docs, metas = get_bm25(
        where
    )

    if not ids:
        return []

    by_id = {
        i: (d, m)
        for i, d, m in zip(
            ids,
            docs,
            metas,
        )
    }

    # --------------------------------------------------------
    # 1. SEMANTIC VECTOR RANKING
    # --------------------------------------------------------

    qvec = embed(query)

    vres = col.query(
        query_embeddings=qvec,
        n_results=min(
            candidate_k,
            len(ids),
        ),
        where=where,
    )

    vec_ids = vres["ids"][0]

    cosine = {
        i: 1 - d
        for i, d in zip(
            vec_ids,
            vres["distances"][0],
        )
    }

    # --------------------------------------------------------
    # 2. BM25 KEYWORD RANKING
    # --------------------------------------------------------

    scores = bm25.get_scores(
        tokenize(query)
    )

    order = sorted(
        range(len(ids)),
        key=lambda i: scores[i],
        reverse=True,
    )

    bm_ids = [
        ids[i]
        for i in order[:candidate_k]
        if scores[i] > 0
    ]

    # --------------------------------------------------------
    # 3. RECIPROCAL RANK FUSION
    # --------------------------------------------------------

    fused = {}

    for ranking, weight in (
        (vec_ids, 1.0),
        (bm_ids, bm25_weight),
    ):

        for rank, cid in enumerate(
            ranking,
            start=1,
        ):

            fused[cid] = (
                fused.get(cid, 0.0)
                + weight / (rrf_k + rank)
            )

    top = sorted(
        fused,
        key=fused.get,
        reverse=True,
    )[:top_k]

    # --------------------------------------------------------
    # Cosine similarity for chunks found only by BM25
    # --------------------------------------------------------

    missing = [
        cid
        for cid in top
        if cid not in cosine
    ]

    if missing:

        emb = col.get(
            ids=missing,
            include=["embeddings"],
        )

        for cid, e in zip(
            emb["ids"],
            emb["embeddings"],
        ):

            cosine[cid] = float(
                np.dot(
                    qvec[0],
                    e,
                )
            )

    # --------------------------------------------------------
    # FINAL RESULTS
    # --------------------------------------------------------

    hits = []

    for cid in top:

        if cosine[cid] >= min_score:

            doc, meta = by_id[cid]

            hits.append(
                {
                    "id": cid,
                    "text": doc,
                    "metadata": meta,
                    "score": round(
                        cosine[cid],
                        3,
                    ),
                    "rrf": round(
                        fused[cid],
                        4,
                    ),
                }
            )

    return hits


# ============================================================
# TERMINAL OUTPUT
# ============================================================

def print_hits(hits):

    if not hits:

        print(
            "No results above the score threshold "
            "-> answer with the fallback phrase."
        )

        return

    for h in hits:

        m = h["metadata"]

        print(
            f"[{h['score']}] "
            f"{m['source']} | "
            f"{m['section']} | "
            f"p.{m['page_number']} "
            f"(printed {m.get('printed_page', '-')})"
        )

        print(
            "   "
            + h["text"]
            .split("\n", 1)[-1][:200]
            .replace("\n", " ")
            + " ...\n"
        )


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":

    ap = argparse.ArgumentParser()

    ap.add_argument(
        "cmd",
        choices=[
            "build",
            "ask",
        ],
    )

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
        "--k",
        type=int,
        default=5,
    )

    ap.add_argument(
        "--vector-only",
        action="store_true",
    )

    a = ap.parse_args()

    if a.cmd == "build":

        build_index()

    else:

        fn = (
            search
            if a.vector_only
            else hybrid_search
        )

        print_hits(
            fn(
                a.question,
                top_k=a.k,
                level=a.level,
                student_type=a.student_type,
                category=a.category,
            )
        )