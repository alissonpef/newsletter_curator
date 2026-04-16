import inspect

from hermes.adapters.imap.imaplib_client import ImaplibClient
from hermes.adapters.ollama.ollama_chat_client import OllamaChatClient
from hermes.adapters.ollama.ollama_embed_client import OllamaEmbedClient
from hermes.adapters.smtp.smtp_client import SmtpClient
from hermes.ports.embedding_port import EmbeddingPort
from hermes.ports.imap_port import ImapPort
from hermes.ports.llm_port import LlmPort
from hermes.ports.smtp_port import SmtpPort


def _method_params(cls, method_name: str) -> list[str]:
    return list(inspect.signature(getattr(cls, method_name)).parameters)


def _assert_signature_compatible(port_cls, adapter_cls, method_name: str) -> None:
    port_params = _method_params(port_cls, method_name)
    adapter_params = _method_params(adapter_cls, method_name)
    assert adapter_params[: len(port_params)] == port_params


def test_imap_adapter_contract() -> None:
    _assert_signature_compatible(ImapPort, ImaplibClient, "fetch_new")


def test_smtp_adapter_contract() -> None:
    _assert_signature_compatible(SmtpPort, SmtpClient, "send_with_attachment")


def test_llm_adapter_contract() -> None:
    _assert_signature_compatible(LlmPort, OllamaChatClient, "chat_structured")


def test_embedding_adapter_contract() -> None:
    _assert_signature_compatible(EmbeddingPort, OllamaEmbedClient, "embed_texts")
