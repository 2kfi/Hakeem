import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np

from rag.schemas import DomainRoute, Entity

logger = logging.getLogger(__name__)

_ROUTER_MODEL = None
_ROUTER_TOKENIZER = None
_DOMAIN_LABELS: list[str] = []


def _load_router(model_path: str, domains: list[str],
                 device: str = "auto"):
    global _ROUTER_MODEL, _ROUTER_TOKENIZER, _DOMAIN_LABELS
    if _ROUTER_MODEL is not None:
        return

    onnx_path = Path(model_path) / "onnx"
    model_file = str(onnx_path / "model.onnx")
    tokenizer_file = str(onnx_path / "tokenizer.json")
    labels_file = str(onnx_path / "labels.json")

    if not os.path.exists(model_file):
        logger.warning("Semantic router ONNX model not found at %s", model_file)
        return
    if not os.path.exists(tokenizer_file):
        logger.warning("Semantic router tokenizer not found at %s", tokenizer_file)
        return

    import onnxruntime as ort
    so = ort.SessionOptions()
    so.log_severity_level = 3
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    providers = ort.get_available_providers()

    _ROUTER_MODEL = ort.InferenceSession(model_file, providers=providers,
                                         sess_options=so)

    from tokenizers import Tokenizer
    _ROUTER_TOKENIZER = Tokenizer.from_file(tokenizer_file)
    _ROUTER_TOKENIZER.enable_truncation(max_length=128)
    _ROUTER_TOKENIZER.enable_padding(pad_id=0, pad_token="[PAD]", length=128)

    if os.path.exists(labels_file):
        with open(labels_file) as f:
            _DOMAIN_LABELS = json.load(f)
    else:
        _DOMAIN_LABELS = domains

    logger.info("Semantic router loaded: %d domains, model=%s",
                len(_DOMAIN_LABELS), model_file)


def _classify(text: str) -> tuple[str, float]:
    if _ROUTER_MODEL is None or _ROUTER_TOKENIZER is None:
        return "", 0.0

    encoded = _ROUTER_TOKENIZER.encode(text)
    input_ids = np.array([encoded.ids], dtype=np.int64)
    attention_mask = np.array([encoded.attention_mask], dtype=np.int64)

    outs = _ROUTER_MODEL.run(
        None,
        {"input_ids": input_ids, "attention_mask": attention_mask},
    )
    logits = outs[0][0]
    probs = np.exp(logits - np.max(logits)) / np.sum(np.exp(logits - np.max(logits)))
    best_idx = int(np.argmax(probs))
    confidence = float(probs[best_idx])

    if best_idx < len(_DOMAIN_LABELS):
        return _DOMAIN_LABELS[best_idx], confidence
    return "", confidence


_MEDICAL_ENTITY_KEYWORDS: dict[str, list[str]] = {
    "drug": ["rifaximin", "lactulose", "spironolactone", "furosemide",
             "metformin", "insulin", "tacrolimus", "interferon"],
    "disease": ["cirrhosis", "hepatitis", "encephalopathy", "nephropathy",
                "neuropathy", "glioblastoma", "parkinson", "alzheimer"],
    "organ": ["liver", "kidney", "brain", "hepatic", "renal", "neural"],
    "gene": ["APOE4", "HLA", "BRCA", "CFTR", "MTHFR"],
    "symptom": ["jaundice", "ascites", "edema", "tremor", "seizure",
                "fatigue", "nausea"],
}


def _extract_keyword_entities(text: str) -> list[Entity]:
    text_lower = text.lower()
    entities: list[Entity] = []
    seen = set()
    for etype, keywords in _MEDICAL_ENTITY_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower and kw not in seen:
                seen.add(kw)
                entities.append(Entity(name=kw, type=etype))
    return entities


def _domain_from_keywords(text: str) -> tuple[str, float]:
    text_lower = text.lower()
    liver_kw = {"liver", "hepatic", "hepatitis", "cirrhosis", "jaundice",
                "ascites", "bilirubin", "rifaximin", "lactulose", "hepatology"}
    kidney_kw = {"kidney", "renal", "nephrology", "dialysis", "creatinine",
                 "glomerular", "nephropathy", "spironolactone", "diuretic"}
    brain_kw = {"brain", "neural", "neurology", "seizure", "stroke",
                "glioblastoma", "neuropathy", "parkinson", "alzheimer"}

    liver_score = sum(1 for kw in liver_kw if kw in text_lower)
    kidney_score = sum(1 for kw in kidney_kw if kw in text_lower)
    brain_score = sum(1 for kw in brain_kw if kw in text_lower)

    domain_map = [
        ("hepatology", liver_score),
        ("nephrology", kidney_score),
        ("neurology", brain_score),
    ]
    domain_map.sort(key=lambda x: x[1], reverse=True)

    best_domain, best_score = domain_map[0]
    total = liver_score + kidney_score + brain_score
    confidence = (best_score / max(total, 1)) * 0.6 + 0.4 * (best_score / max(best_score, 1))
    return best_domain, min(confidence, 0.95)


class HakeemSemanticRouter:
    def __init__(self, model_path: str, domains: list[str],
                 threshold: float = 0.6, device: str = "auto"):
        self._model_path = model_path
        self._domains = domains
        self._threshold = threshold
        self._device = device
        self._loaded = False

    async def initialize(self):
        loop = asyncio.get_event_loop()

        def _init():
            _load_router(self._model_path, self._domains, self._device)

        await loop.run_in_executor(None, _init)
        self._loaded = True
        logger.info("HakeemSemanticRouter initialized (threshold=%.2f, domains=%s)",
                     self._threshold, self._domains)

    async def route(self, query: str) -> list[DomainRoute]:
        if not self._loaded:
            return await self._route_fallback(query)

        loop = asyncio.get_event_loop()

        def _classify_sync():
            domain, confidence = _classify(query)
            entities = _extract_keyword_entities(query)

            if not domain or confidence < self._threshold:
                kw_domain, kw_conf = _domain_from_keywords(query)
                if kw_conf > confidence:
                    domain, confidence = kw_domain, kw_conf

            if not domain or confidence < self._threshold:
                return [DomainRoute(
                    domain=d,
                    confidence=confidence / max(len(self._domains), 1),
                    entities=entities,
                ) for d in self._domains]

            return [DomainRoute(
                domain=domain,
                confidence=confidence,
                entities=entities,
            )]

        return await loop.run_in_executor(None, _classify_sync)

    async def _route_fallback(self, query: str) -> list[DomainRoute]:
        domain, confidence = _domain_from_keywords(query)
        entities = _extract_keyword_entities(query)

        if domain and confidence >= self._threshold:
            return [DomainRoute(domain=domain, confidence=confidence, entities=entities)]

        return [DomainRoute(
            domain=d,
            confidence=confidence / max(len(self._domains), 1),
            entities=entities,
        ) for d in self._domains]

    async def extract_entities(self, query: str) -> list[Entity]:
        return _extract_keyword_entities(query)
