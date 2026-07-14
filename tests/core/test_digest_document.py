from hermes.core.digest_document import (
    clean_markdown_output,
    normalize_heading,
    normalize_signal,
    normalize_spaces,
    parse_summary_markdown,
    strip_accents,
)


def test_normalize_spaces():
    assert normalize_spaces("  hello   world  \n\n\n test ") == "hello world \n\n test"
    assert normalize_spaces("text \r \u00a0 text") == "text text"


def test_strip_accents():
    assert strip_accents("olá, você está bem?") == "ola, voce esta bem?"
    assert strip_accents("ÁÉÍÓÚ") == "AEIOU"


def test_normalize_heading():
    assert normalize_heading("--- Title: HELLO WORLD ---") == "Title: Hello World"
    assert (
        normalize_heading("Already Capitalized And Normalized")
        == "Already Capitalized And Normalized"
    )
    assert normalize_heading("IMPACTO DA SELIC E DO S&P") == "Impacto da Selic e do S&P"


def test_normalize_signal():
    assert normalize_signal(" ALta ") == "Alta"
    assert normalize_signal("forte") == "Alta"
    assert normalize_signal("moderada") == "Média"
    assert normalize_signal("baixo") == "Baixa"
    assert normalize_signal("desconhecido") == "Média"


def test_clean_markdown_output():
    raw = "Some preamble text\n\n# Tese do Dia\nText here"
    assert clean_markdown_output(raw) == "# Tese do Dia\nText here"


def test_parse_summary_markdown():
    markdown = """
# Tese do Dia
This is the thesis.

# Leituras Prioritárias
- Point 1
- Point 2

## Topic 1
This is the summary of topic 1.
Impacto: Very High
Sinal: forte
"""
    result = parse_summary_markdown(markdown)
    assert result["thesis"] == "This is the thesis."
    assert "Point 1" in result["keyPoints"]
    assert "Point 2" in result["keyPoints"]
    assert len(result["topics"]) == 1
    assert result["topics"][0]["title"] == "Topic 1"
    assert result["topics"][0]["summary"] == "This is the summary of topic 1."
    assert result["topics"][0]["impact"] == "Very High"
    assert result["topics"][0]["signal"] == "Alta"
