"""
Ingest pipeline: extract → chunk → embed (ruri-v3-310m) → store (Chroma).

Usage:
    python -m src.ingest --pdf data/raw/001888825.pdf

Produces:
    data/chunks.jsonl   (intermediate, for visual inspection)
    data/chroma/        (Chroma DB directory)
"""
import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

CHROMA_DIR = Path("data/chroma")
CHUNKS_JSONL = Path("data/chunks.jsonl")
COLLECTION_NAME = "jusetu_spec"
# ruri-v3-310m is optimal for Japanese recall but requires GPU (226s/batch on CPU).
# Falling back to multilingual-e5-small for CPU-only environments.
# Production deployment should use ruri-v3-310m with GPU; see README rejection list note.
MODEL_NAME = "intfloat/multilingual-e5-small"

# multilingual-e5-small uses "passage: " / "query: " prefix convention.
DOC_PREFIX = "passage: "


def _load_model():
    import os
    import torch
    from sentence_transformers import SentenceTransformer
    # Use all available CPU cores for PyTorch inference.
    n_threads = os.cpu_count() or 4
    torch.set_num_threads(n_threads)
    logger.info("Loading embedding model: %s (threads=%d)", MODEL_NAME, n_threads)
    model = SentenceTransformer(MODEL_NAME)
    logger.info("Model loaded.")
    return model


def _embed_chunks(model, chunks: list[dict]) -> list[list[float]]:
    texts = [DOC_PREFIX + c["heading"] + "\n" + c["body"] for c in chunks]
    logger.info("Embedding %d chunks with doc prefix...", len(texts))
    embeddings = model.encode(texts, batch_size=8, show_progress_bar=True, normalize_embeddings=True)
    return embeddings.tolist()


def _store_chroma(chunks: list[dict], embeddings: list[list[float]]) -> None:
    import chromadb
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    col = client.create_collection(
        COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    ids = [c["chunk_id"] for c in chunks]
    documents = [c["heading"] + "\n" + c["body"] for c in chunks]
    metadatas = [
        {
            "chunk_id": c["chunk_id"],
            "hierarchy": c["hierarchy"],
            "pages": c["pages"],
            "source_engine": c["source_engine"],
            "doc_type": c["doc_type"],
            "char_count": c["char_count"],
        }
        for c in chunks
    ]

    batch = 500
    for i in range(0, len(chunks), batch):
        col.add(
            ids=ids[i: i + batch],
            embeddings=embeddings[i: i + batch],
            documents=documents[i: i + batch],
            metadatas=metadatas[i: i + batch],
        )
    logger.info("Stored %d chunks in Chroma collection '%s'", len(chunks), COLLECTION_NAME)


def run(pdf_path: str | Path) -> None:
    from src.extract import plumber, pymupdf_ext
    from src.extract.arbiter import arbitrate_pages
    from src.chunker import chunk_pages, write_jsonl

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        logger.error("PDF not found: %s", pdf_path)
        sys.exit(1)

    logger.info("=== extract ===")
    plumber_pages = plumber.extract_pages(pdf_path)
    pymupdf_pages = pymupdf_ext.extract_pages(pdf_path)

    logger.info("=== arbitrate ===")
    pages = arbitrate_pages({"plumber": plumber_pages, "pymupdf": pymupdf_pages})

    logger.info("=== chunk ===")
    chunks = chunk_pages(pages)
    write_jsonl(chunks, CHUNKS_JSONL)

    logger.info("=== embed & store ===")
    model = _load_model()
    embeddings = _embed_chunks(model, chunks)
    _store_chroma(chunks, embeddings)

    logger.info("=== done: %d chunks ingested ===", len(chunks))


def main():
    parser = argparse.ArgumentParser(description="Ingest PDF into Chroma RAG DB")
    parser.add_argument("--pdf", default="data/raw/001888825.pdf", help="Path to PDF file")
    args = parser.parse_args()
    run(args.pdf)


if __name__ == "__main__":
    main()
