from __future__ import annotations

import json
from typing import Any
from urllib import request
from urllib.error import HTTPError, URLError

from ...core.errors import LlmUnavailableError
from ...infra.retries import model_retry


class OllamaChatClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def chat_structured(
        self,
        model: str,
        messages: list[dict[str, str]],
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:
        payload_api_chat = {
            "model": model,
            "messages": messages,
            "format": json_schema,
            "stream": False,
        }

        parsed = self._post_json(path="/api/chat", payload=payload_api_chat)
        message = parsed.get("message") if isinstance(parsed, dict) else None
        content = ""
        if isinstance(message, dict):
            content = message.get("content", "")

        # Newer deployments may expose OpenAI-compatible endpoints only.
        if not content and isinstance(parsed, dict) and parsed.get("error"):
            try:
                parsed = self._post_json(
                    path="/v1/chat/completions",
                    payload={
                        "model": model,
                        "messages": messages,
                        "response_format": {"type": "json_object"},
                        "stream": False,
                    },
                )
            except RuntimeError:
                parsed = {}

            choices = parsed.get("choices", []) if isinstance(parsed, dict) else []
            if choices and isinstance(choices[0], dict):
                choice_message = choices[0].get("message", {})
                if isinstance(choice_message, dict):
                    content = choice_message.get("content", "")

        if not content:
            prompt = "\n\n".join(
                f"{message.get('role', 'user')}: {message.get('content', '')}"
                for message in messages
            )
            generated = self._post_json(
                path="/api/generate",
                payload={
                    "model": model,
                    "prompt": prompt,
                    "format": json_schema,
                    "stream": False,
                },
            )
            content = generated.get("response", "") if isinstance(generated, dict) else ""

        if isinstance(content, dict):
            return content

        if not isinstance(content, str):
            raise LlmUnavailableError("invalid ollama response payload")

        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LlmUnavailableError("ollama returned non-json structured content") from exc

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self._base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            return self._request_json(req)
        except HTTPError as exc:
            if exc.code == 404 and path == "/api/chat":
                return {"error": "not_found"}
            raise LlmUnavailableError("ollama chat request failed") from exc
        except (URLError, TimeoutError, ValueError, json.JSONDecodeError, OSError) as exc:
            raise LlmUnavailableError("ollama chat request failed") from exc

    @model_retry()
    def _request_json(self, req: request.Request) -> dict[str, Any]:
        try:
            with request.urlopen(req, timeout=self._timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
            raise
