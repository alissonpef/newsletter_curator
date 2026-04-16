from __future__ import annotations

import json
from urllib import request
from urllib.error import HTTPError, URLError

from ...core.errors import LlmUnavailableError
from ...infra.retries import model_retry


class OllamaEmbedClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def _normalize_inputs(self, inputs: list[str], max_chars: int) -> list[str]:
        normalized: list[str] = []
        for item in inputs:
            compact = " ".join(str(item).split())
            if len(compact) > max_chars:
                trimmed = compact[:max_chars]
                compact = trimmed.rsplit(" ", 1)[0].strip() or trimmed.strip()
            normalized.append(compact or "sem conteudo")
        return normalized

    def _embed_once(self, model: str, inputs: list[str]) -> list[list[float]]:
        payload = {
            "model": model,
            "input": inputs,
        }
        body = json.dumps(payload).encode("utf-8")

        req = request.Request(
            url=f"{self._base_url}/api/embed",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        parsed = self._request_json(req)
        embeddings = parsed.get("embeddings")
        if not isinstance(embeddings, list):
            raise LlmUnavailableError("invalid embedding response")
        return embeddings

    def embed_texts(self, model: str, inputs: list[str]) -> list[list[float]]:
        if not inputs:
            return []

        # Some embedding models have a small context window. We progressively
        # reduce input size to keep the pipeline resilient with real newsletters.
        for max_chars in (1400, 1000, 700):
            candidate_inputs = self._normalize_inputs(inputs, max_chars=max_chars)
            try:
                return self._embed_once(model=model, inputs=candidate_inputs)
            except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError, OSError):
                continue

        raise LlmUnavailableError("ollama embedding request failed")

    @model_retry()
    def _request_json(self, req: request.Request) -> dict[str, object]:
        with request.urlopen(req, timeout=self._timeout_seconds) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)
