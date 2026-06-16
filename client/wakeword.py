import logging
import sys
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("hakeem-cli")


class WakeWordDetector:
    def __init__(
        self,
        model_paths: Optional[list[str]] = None,
        framework: str = "onnx",
        chunk_size: int = 1280,
        threshold: float = 0.5,
    ):
        self.framework = framework
        self.chunk_size = chunk_size
        self.threshold = threshold
        self.model = None

        try:
            from openwakeword.model import Model
        except ImportError:
            print("ERROR: openwakeword not installed.")
            print(f"  pip install -r client/requirements-{framework}.txt")
            sys.exit(1)

        resolved_paths = []
        if model_paths:
            for mp in model_paths:
                p = Path(mp)
                if p.exists():
                    resolved_paths.append(str(p))
                else:
                    logger.warning("Wake model not found: %s", mp)

        try:
            if resolved_paths:
                self.model = Model(
                    wakeword_models=resolved_paths,
                    inference_framework=framework,
                )
            else:
                self.model = Model(inference_framework=framework)
            logger.info(
                "Loaded %d wake word model(s) [%s]",
                len(self.model.models), framework,
            )
        except Exception as e:
            logger.error("Failed to load openwakeword models: %s", e)
            sys.exit(1)

    def predict(self, audio_chunk: np.ndarray) -> dict[str, float]:
        self.model.predict(audio_chunk)
        scores = {}
        for name in self.model.prediction_buffer:
            buf = self.model.prediction_buffer[name]
            scores[name] = float(buf[-1]) if len(buf) > 0 else 0.0
        return scores

    def any_detected(self, scores: dict[str, float]) -> tuple[bool, str]:
        for name, score in scores.items():
            if score >= self.threshold:
                return True, name
        return False, ""

    def __del__(self):
        if self.model is not None:
            try:
                self.model = None
            except Exception:
                pass
