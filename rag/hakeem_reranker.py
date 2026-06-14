import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np

from rag.schemas import ScoredChunk

logger = logging.getLogger(__name__)

_RERANKER_MODEL = None
_RERANKER_TOKENIZER = None


def _load_reranker(model_path: str, device: str = "auto"):
    global _RERANKER_MODEL, _RERANKER_TOKENIZER
    if _RERANKER_MODEL is not None:
        return

    onnx_path = Path(model_path) / "onnx"
    model_file = str(onnx_path / "model.onnx")
    tokenizer_file = str(onnx_path / "tokenizer.json")

    if not os.path.exists(model_file):
        raise FileNotFoundError(
            f"Reranker ONNX model not found at {model_file}. "
            f"Download bge-reranker-v2-m3 ONNX to {model_path}/onnx/"
        )
    if not os.path.exists(tokenizer_file):
        raise FileNotFoundError(f"Reranker tokenizer not found at {tokenizer_file}")

    import onnxruntime as ort
    so = ort.SessionOptions()
    so.log_severity_level = 3
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    providers = ort.get_available_providers()
    if "CoreMLExecutionProvider" in providers:
        providers.remove("CoreMLExecutionProvider")
    if device == "cpu":
        providers = [p for p in providers if "CUDA" not in p and "TensorRT" not in p]

    _RERANKER_MODEL = ort.InferenceSession(model_file, providers=providers,
                                           sess_options=so)

    from tokenizers import Tokenizer
    _RERANKER_TOKENIZER = Tokenizer.from_file(tokenizer_file)
    _RERANKER_TOKENIZER.enable_truncation(max_length=512)
    _RERANKER_TOKENIZER.enable_padding(pad_id=0, pad_token="[PAD]", length=512)

    logger.info("Cross-encoder reranker loaded from %s", model_file)


def _rerank(query: str, texts: list[str]) -> list[float]:
    if _RERANKER_MODEL is None or _RERANKER_TOKENIZER is None:
        return [1.0] * len(texts)

    concatenated = [f"{query} [SEP] {t}" for t in texts]
    encoded = _RERANKER_TOKENIZER.encode_batch(concatenated)
    input_ids = np.array([e.ids for e in encoded], dtype=np.int64)
    attention_mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)

    outs = _RERANKER_MODEL.run(
        None,
        {"input_ids": input_ids, "attention_mask": attention_mask},
    )
    logits = outs[0]
    scores = [
        float(row[0]) if row.shape[0] == 1 else float(np.mean(row))
        for row in logits
    ]
    return scores


class HakeemReranker:
    def __init__(self, model_path: str, device: str = "auto",
                 top_k: int = 5):
        self._model_path = model_path
        self._device = device
        self._top_k = top_k
        self._loaded = False

    async def initialize(self):
        loop = asyncio.get_event_loop()

        def _init():
            _load_reranker(self._model_path, self._device)

        await loop.run_in_executor(None, _init)
        self._loaded = True
        logger.info("HakeemReranker initialized (top_k=%d)", self._top_k)

    async def rerank(self, query: str, chunks: list[ScoredChunk],
                     top_k: Optional[int] = None) -> list[ScoredChunk]:
        if not chunks:
            return []

        k = top_k or self._top_k
        texts = [c.content for c in chunks]

        loop = asyncio.get_event_loop()

        def _score():
            return _rerank(query, texts)

        scores = await loop.run_in_executor(None, _score)

        for i, chunk in enumerate(chunks):
            if i < len(scores):
                chunk.score = scores[i]

        chunks.sort(key=lambda c: c.score, reverse=True)
        return chunks[:min(k, len(chunks))]
