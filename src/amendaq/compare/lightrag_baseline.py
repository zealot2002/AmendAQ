"""Optional LightRAG column. Uses LightRAG's own index, not the 500-character pipeline.

Generation and the dense model are the same ones locked for the traditional
pipeline. This runner does not change LightRAG's default query mode (`mix`).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

from amendaq.compare.traditional import EMBED_MODEL, QUERY_PREFIX, RERANK_MODEL
from amendaq.llm.openai_compat import OpenAICompatLLM


def available() -> tuple[bool, str]:
    """Check if LightRAG is available via env var path or pip-installed package.
    
    Returns:
        (True, "") if available, or (False, error_message) with actionable hint.
    """
    # Check for AMENDAQ_LIGHTRAG_ROOT environment variable
    lightrag_root_str = os.environ.get("AMENDAQ_LIGHTRAG_ROOT", "").strip()
    if lightrag_root_str:
        lightrag_root = Path(lightrag_root_str)
        if not lightrag_root.is_dir():
            return False, (
                f"AMENDAQ_LIGHTRAG_ROOT is set to '{lightrag_root_str}' but that directory does not exist. "
                f"Please verify the path or unset the variable."
            )
        # Add to sys.path if not already present
        if str(lightrag_root) not in sys.path:
            sys.path.insert(0, str(lightrag_root))
    
    # Try importing lightrag (works for both pip-installed and AMENDAQ_LIGHTRAG_ROOT)
    try:
        import lightrag  # noqa: F401
        return True, ""
    except ImportError:
        return False, (
            "LightRAG is not installed. To use the lightrag baseline, either:\n"
            "  1. Install lightrag-hku: `uv sync --extra compare --extra lightrag` (or `pip install lightrag-hku`)\n"
            "  2. Set AMENDAQ_LIGHTRAG_ROOT=/path/to/LightRAG for a local checkout\n"
            "  3. Run with --systems AmendAQ,traditional for the two-system comparison"
        )
    except Exception as exc:
        return False, f"LightRAG import failed: {exc}"


class LightRAGBaseline:
    def __init__(self, text: str, *, working_dir: Path, llm: OpenAICompatLLM) -> None:
        ok, reason = available()
        if not ok:
            raise RuntimeError(reason)
        from lightrag import LightRAG
        from lightrag.utils import EmbeddingFunc
        from sentence_transformers import SentenceTransformer

        working_dir.mkdir(parents=True, exist_ok=True)
        self._llm = llm
        self._embedder = SentenceTransformer(EMBED_MODEL, device="cpu")
        self.llm_calls = 0
        started = time.perf_counter()

        async def embed(texts, **kwargs):
            context = kwargs.get("context")
            if isinstance(texts, str):
                texts = [texts]
            payload = list(texts)
            if context == "query":
                payload = [QUERY_PREFIX + item for item in payload]
            vectors = self._embedder.encode(
                payload,
                normalize_embeddings=True,
                show_progress_bar=False,
                batch_size=8,
            )
            return np.asarray(vectors, dtype=np.float32)

        async def complete(prompt, system_prompt=None, history_messages=None, **kwargs):
            del kwargs
            self.llm_calls += 1
            parts: list[str] = []
            for message in history_messages or []:
                content = message.get("content") if isinstance(message, dict) else ""
                if content:
                    parts.append(str(content))
            if prompt:
                parts.append(str(prompt))
            user = "\n\n".join(parts)
            system = system_prompt or "你是企业制度问答。只根据给出的资料回答；资料没有的写未检索到。"
            return await asyncio.to_thread(self._llm.complete, system, user)

        self._reranker = None

        async def rerank(query, documents, **kwargs):
            docs = list(documents or [])
            if not docs:
                return []
            from sentence_transformers import CrossEncoder

            if self._reranker is None:
                self._reranker = CrossEncoder(RERANK_MODEL, device="cpu")
            scores = self._reranker.predict(
                [(query, doc) for doc in docs],
                show_progress_bar=False,
            )
            order = sorted(range(len(docs)), key=lambda pos: float(scores[pos]), reverse=True)
            top_n = kwargs.get("top_n")
            if isinstance(top_n, int) and top_n > 0:
                order = order[:top_n]
            return [
                {"index": pos, "relevance_score": float(scores[pos])}
                for pos in order
            ]

        self._rag = LightRAG(
            working_dir=str(working_dir),
            llm_model_func=complete,
            rerank_model_func=rerank,
            embedding_func=EmbeddingFunc(
                embedding_dim=1024,
                max_token_size=512,
                func=embed,
                model_name=EMBED_MODEL,
                supports_asymmetric=True,
            ),
        )
        graph = working_dir / "graph_chunk_entity_relation.graphml"
        meta_path = working_dir / "index_meta.json"
        asyncio.run(self._rag.initialize_storages())
        if graph.is_file() and graph.stat().st_size > 1000 and meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self.index_seconds = float(meta.get("index_s") or 0)
            self.index_llm_calls = int(meta.get("index_llm_calls") or 0)
            return
        self._rag.insert(text)
        self.index_seconds = round(time.perf_counter() - started, 3)
        self.index_llm_calls = self.llm_calls
        meta_path.write_text(
            json.dumps(
                {"index_s": self.index_seconds, "index_llm_calls": self.index_llm_calls},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def answer(self, question: str) -> dict:
        from lightrag import QueryParam

        before_prompt = self._llm.usage_totals["prompt_tokens"]
        before_completion = self._llm.usage_totals["completion_tokens"]
        before_calls = self.llm_calls
        started = time.perf_counter()
        text = self._rag.query(
            question,
            param=QueryParam(mode="mix", stream=False, enable_rerank=True),
        )
        finished = time.perf_counter()
        if not isinstance(text, str):
            text = str(text or "")
        return {
            "answer": text,
            "retrieve_s": None,
            "generate_s": None,
            "total_s": round(finished - started, 3),
            "llm_calls": self.llm_calls - before_calls,
            "prompt_tokens": self._llm.usage_totals["prompt_tokens"] - before_prompt,
            "completion_tokens": self._llm.usage_totals["completion_tokens"] - before_completion,
        }

    def close(self) -> None:
        """Release in-memory storages so a second corpus can run in one process."""
        rag = getattr(self, "_rag", None)
        if rag is None:
            return
        try:
            asyncio.run(rag.finalize_storages())
        except RuntimeError as exc:
            if "Event loop is closed" not in str(exc):
                raise
        except Exception:
            pass
        self._rag = None
