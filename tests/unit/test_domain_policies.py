from datetime import date

from hermes.core.policies import (
    build_content_hash,
    estimate_tokens,
    is_allowed_sender,
    is_promotional_noise,
    normalize_sender_email,
    resolve_namespace,
    should_skip_email,
)


def test_build_content_hash_is_stable_for_whitespace_variation() -> None:
    left = build_content_hash("Hello   world\nthis is a test")
    right = build_content_hash("Hello world this is a test")
    assert left == right


def test_should_skip_email_for_existing_message_id() -> None:
    assert should_skip_email(
        message_id="<abc@example.com>",
        content_hash="hash-1",
        processed_message_ids={"<abc@example.com>"},
        processed_hashes=set(),
    )


def test_should_skip_email_for_existing_content_hash() -> None:
    assert should_skip_email(
        message_id=None,
        content_hash="hash-2",
        processed_message_ids=set(),
        processed_hashes={"hash-2"},
    )


def test_is_promotional_noise_by_keyword() -> None:
    assert is_promotional_noise(
        sender="promo@example.com",
        subject="Oferta imperdivel",
        body_text="Aproveite o desconto de hoje",
        negative_keywords=["desconto", "unsubscribe"],
    )


def test_resolve_namespace_uses_date_reference() -> None:
    assert resolve_namespace(date(2026, 4, 14)) == "daily::2026-04-14"


def test_estimate_tokens_non_empty_text() -> None:
    assert estimate_tokens("um dois tres quatro") > 0


def test_normalize_sender_email_extracts_address() -> None:
    assert normalize_sender_email("NeoFeed <newsletter@neofeed.com.br>") == "newsletter@neofeed.com.br"


def test_is_allowed_sender_matches_normalized_email() -> None:
    assert is_allowed_sender(
        sender="InfoMoney <relacionamento@info.infomoney.com.br>",
        allowed_senders=["newsletter@neofeed.com.br", "relacionamento@info.infomoney.com.br"],
    )


def test_is_allowed_sender_rejects_non_listed_sender() -> None:
    assert not is_allowed_sender(
        sender="created@dollarbill.com.br",
        allowed_senders=["newsletter@neofeed.com.br", "relacionamento@info.infomoney.com.br"],
    )
