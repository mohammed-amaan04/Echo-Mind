"""Pytest configuration for the EchoMind test suite.

Patches ``SentenceTransformer`` with a lightweight offline mock so the tests
can run without downloading model weights from HuggingFace.  The mock uses a
bag-of-words hash-trick to produce 384-dimensional unit vectors whose cosine
similarity reflects word overlap, which is sufficient for the retrieval tests.
"""

from __future__ import annotations

import hashlib

import numpy as np
import sentence_transformers


class _OfflineEmbeddingModel:
    """Deterministic, offline drop-in for SentenceTransformer.

    Embeds text by mapping each whitespace-delimited token to a bucket in a
    384-dim vector (SHA-256 hash mod 384) and L2-normalising the result.
    Texts that share tokens therefore have higher cosine similarity, which is
    enough for the retrieval layer tests.
    """

    DIM = 384

    def __init__(self, model_name_or_path: str, **kwargs) -> None:
        self._model_name = model_name_or_path

    # ------------------------------------------------------------------
    # Public API (mirrors SentenceTransformer)
    # ------------------------------------------------------------------

    def encode(
        self,
        sentences,
        normalize_embeddings: bool = True,
        **kwargs,
    ) -> np.ndarray:
        if isinstance(sentences, str):
            vec = self._embed(sentences)
            if normalize_embeddings:
                vec = self._normalise(vec)
            return vec
        # list / iterable of strings
        vecs = [self._embed(s) for s in sentences]
        arr = np.stack(vecs)
        if normalize_embeddings:
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1.0, norms)
            arr = arr / norms
        return arr

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self.DIM, dtype=np.float32)
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode()).hexdigest()
            idx = int(digest, 16) % self.DIM
            vec[idx] += 1.0
        return vec

    @staticmethod
    def _normalise(vec: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec


# ---------------------------------------------------------------------------
# Patch before any test module is imported
# ---------------------------------------------------------------------------

sentence_transformers.SentenceTransformer = _OfflineEmbeddingModel  # type: ignore[attr-defined]
