from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List


SECTION_KEYS = {
    "tese do dia": "thesis",
    "panorama executivo": "executiveSummary",
    "leituras prioritarias": "keyPoints",
    "leituras prioritárias": "keyPoints",
    "temas em foco": "topics",
    "fechamento": "closing",
}

SIGNAL_MAP = {
    "alta": "Alta",
    "alto": "Alta",
    "forte": "Alta",
    "media": "Média",
    "média": "Média",
    "moderada": "Média",
    "moderado": "Média",
    "baixa": "Baixa",
    "baixo": "Baixa",
}


def normalize_spaces(text: str) -> str:
    text = text or ""
    text = re.sub(r"[\u200b\u200c\u200d\ufeff\u2028\u2029]", "", text)

    # Fix hyphenated word breaks: "inter- \n nacional" -> "internacional"
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)

    text = text.replace("\r", "")
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_heading(text: str) -> str:
    candidate = normalize_spaces(text).strip(":- ")
    if not candidate:
        return ""

    alpha_chars = [ch for ch in candidate if ch.isalpha()]
    uppercase_ratio = 0.0
    if alpha_chars:
        uppercase_ratio = sum(1 for ch in alpha_chars if ch.isupper()) / len(
            alpha_chars
        )

    if uppercase_ratio < 0.55:
        return candidate

    lowercase_words = {
        "a",
        "ao",
        "aos",
        "as",
        "com",
        "da",
        "das",
        "de",
        "do",
        "dos",
        "e",
        "em",
        "na",
        "nas",
        "no",
        "nos",
        "o",
        "os",
        "ou",
        "para",
        "por",
        "sem",
        "sob",
        "um",
        "uma",
    }

    words = []
    for index, raw_word in enumerate(candidate.lower().split()):
        if index > 0 and raw_word in lowercase_words:
            words.append(raw_word)
            continue
        words.append(raw_word.capitalize())
    title = " ".join(words)
    title = re.sub(r"\bIa\b", "IA", title)
    title = re.sub(r"\bBc\b", "BC", title)
    title = re.sub(r"\bS&p\b", "S&P", title)
    title = re.sub(r"\bOpenai\b", "OpenAI", title)
    title = re.sub(r"\bChatgpts\b", "ChatGPTs", title)
    title = re.sub(r"\bSelic\b", "Selic", title)
    return title


def empty_summary() -> Dict[str, Any]:
    return {
        "thesis": "",
        "executiveSummary": "",
        "keyPoints": [],
        "topics": [],
        "closing": "",
        "rawMarkdown": "",
        "plainText": "",
        "ttsScript": "",
        "sourceCount": 0,
        "paragraphCount": 0,
    }


def _topic_to_plain_text(topic: Dict[str, Any]) -> str:
    summary = normalize_spaces(topic.get("summary", ""))
    impact = normalize_spaces(topic.get("impact", ""))
    title = normalize_heading(topic.get("title", "")) or "Tema"
    parts = [f"{title}. {summary}".strip()]
    if impact:
        parts.append(f"Impacto: {impact}")
    return " ".join(part for part in parts if part).strip()


def summary_to_plain_text(summary_data: Dict[str, Any]) -> str:
    parts: List[str] = []

    thesis = normalize_spaces(summary_data.get("thesis", ""))
    executive_summary = normalize_spaces(summary_data.get("executiveSummary", ""))
    closing = normalize_spaces(summary_data.get("closing", ""))
    key_points = [
        normalize_spaces(item)
        for item in summary_data.get("keyPoints", [])
        if normalize_spaces(item)
    ]
    topics = [topic for topic in summary_data.get("topics", []) if topic]

    if thesis:
        parts.append(thesis)
    if executive_summary:
        parts.append(executive_summary)
    if key_points:
        parts.append("Pontos essenciais: " + "; ".join(key_points) + ".")
    for topic in topics:
        topic_text = _topic_to_plain_text(topic)
        if topic_text:
            parts.append(topic_text)
    if closing:
        parts.append(closing)

    return normalize_spaces("\n\n".join(part for part in parts if part))


def _dedupe_text_items(items: Iterable[str]) -> List[str]:
    unique: List[str] = []
    seen = set()
    for item in items:
        candidate = normalize_spaces(item)
        key = re.sub(r"[^a-z0-9]+", "", strip_accents(candidate).lower())
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def normalize_signal(signal: str) -> str:
    candidate = strip_accents(normalize_spaces(signal)).lower()
    return SIGNAL_MAP.get(candidate, "Média")


def clean_markdown_output(markdown: str) -> str:
    markdown = normalize_spaces(markdown)
    if not markdown:
        return ""

    first_heading = markdown.find("# ")
    if first_heading > 0:
        markdown = markdown[first_heading:]

    markdown = re.sub(r"\n[ \t]*[-*][ \t]*\n", "\n", markdown)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip()


def _append_section_line(store: Dict[str, Any], key: str | None, line: str) -> None:
    if not key:
        return

    if key == "keyPoints":
        if line.startswith("- "):
            store[key].append(normalize_spaces(line[2:]))
        elif line:
            store[key].append(normalize_spaces(line.lstrip("-* ")))
        return

    if key == "topics":
        return

    existing = store[key]
    store[key] = normalize_spaces(f"{existing}\n\n{line}" if existing else line)


def parse_summary_markdown(markdown: str) -> Dict[str, Any]:
    summary_data = empty_summary()
    markdown = clean_markdown_output(markdown)
    summary_data["rawMarkdown"] = markdown

    if not markdown:
        return summary_data

    current_section: str | None = None
    current_topic: Dict[str, Any] | None = None

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("## "):
            if current_topic:
                current_topic["summary"] = normalize_spaces(
                    current_topic.get("summary", "")
                )
                current_topic["impact"] = normalize_spaces(
                    current_topic.get("impact", "")
                )
                summary_data["topics"].append(current_topic)
            current_topic = {
                "title": normalize_heading(line[3:]),
                "summary": "",
                "impact": "",
                "signal": "Média",
            }
            current_section = "topics"
            continue

        if line.startswith("# "):
            if current_topic:
                current_topic["summary"] = normalize_spaces(
                    current_topic.get("summary", "")
                )
                current_topic["impact"] = normalize_spaces(
                    current_topic.get("impact", "")
                )
                summary_data["topics"].append(current_topic)
                current_topic = None

            label = strip_accents(line[2:].strip()).lower()
            current_section = SECTION_KEYS.get(label)
            continue

        if current_topic is not None:
            lowered = strip_accents(line).lower()
            if lowered.startswith("impacto:"):
                current_topic["impact"] = normalize_spaces(line.split(":", 1)[1])
            elif lowered.startswith("sinal:"):
                current_topic["signal"] = normalize_signal(line.split(":", 1)[1])
            else:
                joined = (
                    f"{current_topic['summary']}\n\n{line}"
                    if current_topic["summary"]
                    else line
                )
                current_topic["summary"] = joined
            continue

        _append_section_line(summary_data, current_section, line)

    if current_topic:
        current_topic["summary"] = normalize_spaces(current_topic.get("summary", ""))
        current_topic["impact"] = normalize_spaces(current_topic.get("impact", ""))
        summary_data["topics"].append(current_topic)

    summary_data["thesis"] = normalize_spaces(summary_data["thesis"])
    summary_data["executiveSummary"] = normalize_spaces(
        summary_data["executiveSummary"]
    )
    summary_data["closing"] = normalize_spaces(summary_data["closing"])
    summary_data["keyPoints"] = _dedupe_text_items(summary_data["keyPoints"])
    summary_data["topics"] = [
        {
            "title": normalize_heading(topic.get("title", "")) or "Tema",
            "summary": normalize_spaces(topic.get("summary", "")),
            "impact": normalize_spaces(topic.get("impact", "")),
            "signal": normalize_signal(topic.get("signal", "")),
        }
        for topic in summary_data["topics"]
        if normalize_spaces(topic.get("title", ""))
        or normalize_spaces(topic.get("summary", ""))
    ]
    unique_topics = []
    seen_topics = set()
    for topic in summary_data["topics"]:
        topic_key = re.sub(
            r"[^a-z0-9]+",
            "",
            strip_accents(f"{topic['title']} {topic['summary']}").lower(),
        )
        if not topic_key or topic_key in seen_topics:
            continue
        seen_topics.add(topic_key)
        unique_topics.append(topic)
    summary_data["topics"] = unique_topics
    summary_data["plainText"] = summary_to_plain_text(summary_data)
    summary_data["ttsScript"] = summary_data["plainText"]
    summary_data["paragraphCount"] = len(
        [
            part
            for part in re.split(r"\n\n+", summary_data["plainText"])
            if normalize_spaces(part)
        ]
    )
    return summary_data


def build_fallback_summary(source_packets: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    packets = [packet for packet in source_packets if packet]
    summary_data = empty_summary()
    summary_data["sourceCount"] = len(packets)

    if not packets:
        return summary_data

    lead_titles = [
        normalize_heading(packet.get("title", ""))
        for packet in packets[:10]
        if packet.get("title")
    ]
    lead_highlights = [
        normalize_spaces(paragraph)
        for packet in packets
        for paragraph in packet.get("highlights", [])[:2]
        if normalize_spaces(paragraph)
    ]

    summary_data["thesis"] = (
        lead_highlights[0]
        if lead_highlights
        else (lead_titles[0] if lead_titles else "")
    )
    executive_summary_parts: List[str] = []
    for packet in packets[1:4]:
        packet_highlights = [
            normalize_spaces(paragraph)
            for paragraph in packet.get("highlights", [])
            if normalize_spaces(paragraph)
        ]
        if packet_highlights:
            executive_summary_parts.append(packet_highlights[0])
        elif packet.get("title"):
            executive_summary_parts.append(normalize_heading(packet["title"]))

    if not executive_summary_parts:
        executive_summary_parts = lead_highlights[1:4] or lead_titles[1:4]

    summary_data["executiveSummary"] = " ".join(executive_summary_parts).strip()
    summary_data["keyPoints"] = _dedupe_text_items(
        lead_highlights[:5] or lead_titles[:5]
    )

    topics: List[Dict[str, Any]] = []

    for packet in packets[:20]:
        title = normalize_heading(packet.get("title", "")) or "Radar"
        highlights = packet.get("highlights", [])
        if not highlights:
            continue

        # Better summary extraction: join paragraphs but check for hyphenated word breaks
        summary_raw = packet.get("summary") or " ".join(highlights[:2]).strip()
        summary = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", summary_raw) # Join broken words
        summary = re.sub(r"\s+", " ", summary).strip()

        # Better impact extraction: avoid repeating the title
        impact_raw = packet.get("impact") or (
            highlights[2]
            if len(highlights) > 2
            else ""
        )
        impact = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", impact_raw)
        impact = re.sub(r"\s+", " ", impact).strip().lstrip(" ,;:-.")

        # If impact is too short or just repeats the title, use a generic one or none
        if not impact or len(impact) < 10 or impact.lower() in title.lower():
            impact = "Ponto de atenção para investidores."

        from difflib import SequenceMatcher

        is_duplicate = False
        for et in topics:
            if SequenceMatcher(None, title.lower(), et["title"].lower()).ratio() > 0.8:
                is_duplicate = True
                break
            if (
                SequenceMatcher(
                    None, summary[:100].lower(), et["summary"][:100].lower()
                ).ratio()
                > 0.7
            ):
                is_duplicate = True
                break

        if is_duplicate:
            continue

        topics.append(
            {
                "title": title,
                "summary": summary[:350],
                "impact": impact,
                "signal": "Média",
            }
        )

        if len(topics) >= 12:
            break

    summary_data["topics"] = topics
    summary_data["closing"] = (
        "O acompanhamento do dia pede atenção à evolução desses temas e à reação dos mercados locais e globais."
    )

    summary_data["plainText"] = summary_to_plain_text(summary_data)
    summary_data["ttsScript"] = summary_data["plainText"]
    summary_data["paragraphCount"] = len(
        [
            part
            for part in re.split(r"\n\n+", summary_data["plainText"])
            if normalize_spaces(part)
        ]
    )
    return summary_data
