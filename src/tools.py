"""
Agent tools: search_chunks and read_section.

TOOLS: provider-agnostic tool definitions for passing to LLM adapters.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CHROMA_DIR = Path("data/chroma")
CHUNKS_JSONL = Path("data/chunks.jsonl")
COLLECTION_NAME = "kitei_spec"
MODEL_NAME = "cl-nagoya/ruri-v3-310m"

# Query-side prefix for ruri-v3-310m.
# Source: cl-nagoya/ruri-v3-310m HuggingFace model card (verified 2026-08-04).
QUERY_PREFIX = "クエリ: "

TOOLS = [
    {
        "name": "search_chunks",
        "description": (
            "条文テキストをベクトル検索し、関連チャンクを返す。"
            "返値には chunk_id, hierarchy, heading, body, pages, domain, refs が含まれる。"
            "refsは本文中に出現する他条文・表への参照先。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "検索クエリ（日本語）"},
                "domain": {
                    "type": "string",
                    "description": "系統フィルタ（electric / civil / arch 等）。省略で全系統対象",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返す件数（デフォルト3）",
                    "default": 3,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_section",
        "description": (
            "条番号または階層パスで条文全文を返す。"
            "hierarchy には '1.7.3' のような条番号、または '第2編/第1章/第3節/1.7.3' のような完全パスを指定する。"
            "部分一致（末尾一致）で検索するため条番号のみでも機能する。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doc_slug": {
                    "type": "string",
                    "description": "文書スラッグ（例: denki-setsubi）",
                },
                "hierarchy": {
                    "type": "string",
                    "description": "条番号（例: 1.7.3）または完全階層パス",
                },
            },
            "required": ["doc_slug", "hierarchy"],
        },
    },
]


_embed_model = None
_tfidf_index = None  # fallback when model download fails


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embed_model = SentenceTransformer(MODEL_NAME)
        except Exception as exc:
            logger.warning("Failed to load embedding model (%s); TF-IDF fallback active.", exc)
            _embed_model = "tfidf"  # sentinel
    return _embed_model


def _get_tfidf_index():
    global _tfidf_index
    if _tfidf_index is None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        import numpy as np

        chunks = []
        if CHUNKS_JSONL.exists():
            with open(CHUNKS_JSONL, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        chunks.append(json.loads(line))

        texts = [c["heading"] + "\n" + c["body"] for c in chunks]
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), max_features=30000)
        matrix = vec.fit_transform(texts)
        _tfidf_index = {"chunks": chunks, "vectorizer": vec, "matrix": matrix}
        logger.info("TF-IDF index built (%d chunks)", len(chunks))
    return _tfidf_index


def _search_tfidf(query: str, domain: str | None, top_k: int) -> list[dict]:
    import numpy as np

    idx = _get_tfidf_index()
    chunks = idx["chunks"]
    qvec = idx["vectorizer"].transform([query])
    scores = (idx["matrix"] @ qvec.T).toarray().flatten()

    if domain:
        for i, c in enumerate(chunks):
            if c.get("domain") != domain:
                scores[i] = -1.0

    top_ids = np.argsort(scores)[::-1][:top_k]
    hits = []
    for i in top_ids:
        if scores[i] <= 0:
            continue
        c = chunks[i]
        hits.append(
            {
                "chunk_id": c.get("chunk_id", ""),
                "hierarchy": c.get("hierarchy", ""),
                "heading": c.get("heading", ""),
                "body": c.get("body", ""),
                "pages": c.get("pages", ""),
                "domain": c.get("domain", ""),
                "refs": c.get("refs", []),
            }
        )
    return hits


def search_chunks(query: str, domain: str | None = None, top_k: int = 3) -> list[dict]:
    model = _get_embed_model()

    if model == "tfidf":
        return _search_tfidf(query, domain, top_k)

    vec = model.encode([QUERY_PREFIX + query], normalize_embeddings=True).tolist()[0]

    import chromadb

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    col = client.get_collection(COLLECTION_NAME)

    where = {"domain": domain} if domain else None
    results = col.query(
        query_embeddings=[vec],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas"],
    )

    hits = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        lines = doc.split("\n", 1)
        hits.append(
            {
                "chunk_id": meta.get("chunk_id", ""),
                "hierarchy": meta.get("hierarchy", ""),
                "heading": lines[0] if lines else "",
                "body": lines[1] if len(lines) > 1 else "",
                "pages": meta.get("pages", ""),
                "domain": meta.get("domain", ""),
                "refs": json.loads(meta.get("refs", "[]")),
            }
        )
    return hits


def read_section(doc_slug: str, hierarchy: str) -> str:
    chunks = []
    if CHUNKS_JSONL.exists():
        with open(CHUNKS_JSONL, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    chunks.append(json.loads(line))

    slug_chunks = [c for c in chunks if c.get("chunk_id", "").startswith(doc_slug)]

    # Exact hierarchy match
    for chunk in slug_chunks:
        if chunk.get("hierarchy") == hierarchy:
            return chunk["heading"] + "\n" + chunk["body"]

    # Partial match: hierarchy ends with "/article_num" or equals article_num
    for chunk in slug_chunks:
        h = chunk.get("hierarchy", "")
        if h.endswith("/" + hierarchy) or h == hierarchy:
            return chunk["heading"] + "\n" + chunk["body"]

    return f"[条文が見つかりません: doc_slug={doc_slug}, hierarchy={hierarchy}]"
