# Arkan Fakoseh -  @2kfi on github
import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np

from llama_index.core.embeddings import BaseEmbedding

logger = logging.getLogger(__name__)

_ONNX_SESSION = None
_TOKENIZER = None


def _load_onnx_session(model_dir: str, device: str = "auto"):
    global _TOKENIZER, _ONNX_SESSION
    if _ONNX_SESSION is not None:
        return

    from tokenizers import Tokenizer
    import onnxruntime as ort

    onnx_path = Path(model_dir) / "onnx"
    model_file = str(onnx_path / "model.onnx")
    tokenizer_file = str(onnx_path / "tokenizer.json")

    if not os.path.exists(model_file):
        raise FileNotFoundError(
            f"ONNX model not found at {model_file}. "
            f"Download it: place onnx.tar.gz in {model_dir} and extract."
        )
    if not os.path.exists(tokenizer_file):
        raise FileNotFoundError(f"Tokenizer not found at {tokenizer_file}")

    so = ort.SessionOptions()
    so.log_severity_level = 3
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    providers = ort.get_available_providers()
    if "CoreMLExecutionProvider" in providers:
        providers.remove("CoreMLExecutionProvider")

    if device == "cpu":
        providers = [p for p in providers if "CUDA" not in p and "TensorRT" not in p]
        logger.info("ONNX providers (CPU-only): %s", providers)
    elif device == "cuda":
        if "CUDAExecutionProvider" in providers:
            providers.remove("CUDAExecutionProvider")
            providers = ["CUDAExecutionProvider"] + providers
            logger.info("ONNX providers (CUDA preferred): %s", providers)

    _ONNX_SESSION = ort.InferenceSession(model_file, providers=providers, sess_options=so)

    _TOKENIZER = Tokenizer.from_file(tokenizer_file)
    _TOKENIZER.enable_truncation(max_length=256)
    _TOKENIZER.enable_padding(pad_id=0, pad_token="[PAD]", length=256)


def _embed(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    if _ONNX_SESSION is None or _TOKENIZER is None:
        raise RuntimeError("ONNX model not loaded")

    all_embeddings: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        encoded = _TOKENIZER.encode_batch(batch)
        input_ids = np.array([b.ids for b in encoded], dtype=np.int64)
        attention_mask = np.array([b.attention_mask for b in encoded], dtype=np.int64)
        token_type_ids = np.array([b.type_ids for b in encoded], dtype=np.int64)

        outs = _ONNX_SESSION.run(
            None,
            {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": token_type_ids,
            },
        )
        token_emb = outs[0]
        mask = np.expand_dims(attention_mask.astype(np.float32), axis=-1)
        embeddings = np.sum(token_emb * mask, axis=1) / np.maximum(np.sum(mask, axis=1), 1e-9)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        embeddings = embeddings / norms
        all_embeddings.extend(embeddings.tolist())
    return all_embeddings


class OnnxEmbedding(BaseEmbedding):
    def __init__(
        self,
        model_dir: str,
        device: str = "auto",
        embed_batch_size: int = 32,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._model_dir = model_dir
        self._device = device
        self._embed_batch_size = embed_batch_size

    @classmethod
    def class_name(cls) -> str:
        return "hakeem.onnx_minilm_l6_v2"

    def _get_query_embedding(self, query: str) -> list[float]:
        return _embed([query], batch_size=self._embed_batch_size)[0]

    def _get_text_embedding(self, text: str) -> list[float]:
        return _embed([text], batch_size=self._embed_batch_size)[0]

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        return _embed(texts, batch_size=self._embed_batch_size)

    async def _aget_query_embedding(self, query: str) -> list[float]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._get_query_embedding, query
        )

    async def _aget_text_embedding(self, text: str) -> list[float]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._get_text_embedding, text
        )

    async def _aget_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._get_text_embeddings, texts
        )
