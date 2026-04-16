from typing import Any, Protocol


class LlmPort(Protocol):
    def chat_structured(
        self,
        model: str,
        messages: list[dict[str, str]],
        json_schema: dict[str, Any],
    ) -> dict[str, Any]: ...
