"""Locked traditional pipeline: fixed characters, BM25, dense, open reranker.

Embedding and reranker are used only here. Generation goes through the same
AmendAQ LLM client as the system under test. If a pinned model cannot load, this
module fails instead of dropping down to a weaker embedder.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path

import numpy as np

from amendaq.compare.chunking import CHUNK_CHARS, CHUNK_OVERLAP, chunk_chars
from amendaq.llm.openai_compat import OpenAICompatLLM

EMBED_MODEL = "BAAI/bge-large-zh-v1.5"
EMBED_REVISION = "79e7739b6ab944e86d6171e44d24c997fc1e0116"
RERANK_MODEL = "BAAI/bge-reranker-large"
RERANK_REVISION = "55611d7bca2a7133960a6d3b71e083071bbfc312"
QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："
BM25_TOP = 20
DENSE_TOP = 20
RRF_K = 60
RERANK_TOP = 5
DEVICE = "cpu"

SYSTEM = """你是企业制度问答。只根据用户消息里的检索片段回答，不要使用片段以外的制度常识。
片段里已经写明的义务和数字，按原文下结论。题目里已经发生的事实，用来对照片段中的条件。
片段里没有的制度、金额、比例、期限，写「未检索到」，不要编造。
用简体中文，先写结论。"""


def pipeline_lock() -> dict:
    return {
        "chunk_chars": CHUNK_CHARS,
        "chunk_overlap": CHUNK_OVERLAP,
        "bm25_top": BM25_TOP,
        "dense_top": DENSE_TOP,
        "rrf_k": RRF_K,
        "rerank_top": RERANK_TOP,
        "embed_model": EMBED_MODEL,
        "embed_revision": hf_revision(EMBED_MODEL) if hf_revision(EMBED_MODEL) != "unknown" else EMBED_REVISION,
        "rerank_model": RERANK_MODEL,
        "rerank_revision": hf_revision(RERANK_MODEL) if hf_revision(RERANK_MODEL) != "unknown" else RERANK_REVISION,
        "query_prefix": QUERY_PREFIX,
        "device": DEVICE,
        "tokenize": "jieba.lcut_for_search",
        "fusion": "RRF",
    }


def hf_revision(model_id: str) -> str:
    folder = "models--" + model_id.replace("/", "--")
    ref = Path.home() / ".cache" / "huggingface" / "hub" / folder / "refs" / "main"
    if ref.is_file():
        return ref.read_text(encoding="utf-8").strip() or "unknown"
    return "unknown"


def _tokenize(text: str) -> list[str]:
    import jieba

    jieba.setLogLevel(logging.ERROR)
    return [tok.strip() for tok in jieba.lcut_for_search(text) if tok.strip()]


def _rrf(rankings: list[list[int]], k: int = RRF_K) -> list[int]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, index in enumerate(ranking, start=1):
            scores[index] = scores.get(index, 0.0) + 1.0 / (k + rank)
    return [index for index, _score in sorted(scores.items(), key=lambda item: -item[1])]


class TraditionalRAG:
    def __init__(self, text: str, *, cache_dir: Path) -> None:
        from sentence_transformers import SentenceTransformer

        self.text = text
        self.chunks = chunk_chars(text)
        if not self.chunks:
            raise RuntimeError("traditional RAG corpus is empty")
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = cache_dir
        from rank_bm25 import BM25Okapi

        self._bm25 = BM25Okapi([_tokenize(chunk) for chunk in self.chunks])
        started = time.perf_counter()
        self._embedder = SentenceTransformer(EMBED_MODEL, device=DEVICE)
        self._matrix = self._document_matrix()
        self.index_seconds = round(time.perf_counter() - started, 3)
        self._reranker = None

    def _document_matrix(self) -> np.ndarray:
        digest = hashlib.sha256(self.text.encode("utf-8")).hexdigest()[:16]
        revision = hf_revision(EMBED_MODEL) or "pending"
        path = self.cache_dir / f"dense-{revision}-{digest}.npy"
        meta_path = self.cache_dir / f"dense-{revision}-{digest}.json"
        if path.is_file() and meta_path.is_file():
            matrix = np.load(path)
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if (
                matrix.shape[0] == len(self.chunks)
                and meta.get("embed_model") == EMBED_MODEL
            ):
                return matrix
        matrix = self._embedder.encode(
            self.chunks,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=8,
        )
        matrix = np.asarray(matrix, dtype=np.float32)
        np.save(path, matrix)
        meta_path.write_text(
            json.dumps(
                {"embed_model": EMBED_MODEL, "revision": hf_revision(EMBED_MODEL)},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return matrix

    def _rerank(self, question: str, indexes: list[int]) -> list[int]:
        if not indexes:
            return []
        from sentence_transformers import CrossEncoder

        if self._reranker is None:
            self._reranker = CrossEncoder(RERANK_MODEL, device=DEVICE)
        pairs = [(question, self.chunks[index]) for index in indexes]
        scores = self._reranker.predict(pairs, show_progress_bar=False)
        order = sorted(range(len(indexes)), key=lambda pos: float(scores[pos]), reverse=True)
        return [indexes[pos] for pos in order[:RERANK_TOP]]

    def retrieve(self, question: str) -> list[int]:
        bm25_scores = self._bm25.get_scores(_tokenize(question))
        bm25_order = [int(i) for i in np.argsort(bm25_scores)[::-1][:BM25_TOP]]
        query_vec = self._embedder.encode(
            QUERY_PREFIX + question,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        query_vec = np.asarray(query_vec, dtype=np.float32)
        dense_scores = self._matrix @ query_vec
        dense_order = [int(i) for i in np.argsort(dense_scores)[::-1][:DENSE_TOP]]
        return self._rerank(question, _rrf([bm25_order, dense_order]))

    def answer(self, question: str, llm: OpenAICompatLLM) -> dict:
        started = time.perf_counter()
        indexes = self.retrieve(question)
        retrieved_at = time.perf_counter()
        blocks = [
            f"[片段{rank}]\n{self.chunks[index]}"
            for rank, index in enumerate(indexes, start=1)
        ]
        user = f"问题：{question}\n\n检索片段：\n" + "\n\n".join(blocks)
        before = dict(llm.usage_totals)
        text = llm.complete(SYSTEM, user)
        after = llm.usage_totals
        finished = time.perf_counter()
        return {
            "answer": text,
            "retrieve_s": round(retrieved_at - started, 3),
            "generate_s": round(finished - retrieved_at, 3),
            "total_s": round(finished - started, 3),
            "llm_calls": 1,
            "prompt_tokens": after["prompt_tokens"] - before["prompt_tokens"],
            "completion_tokens": after["completion_tokens"] - before["completion_tokens"],
            "chunk_indexes": indexes,
        }
