from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List

from hermes.core.digest_document import normalize_heading, normalize_spaces


NOISE_PATTERNS = [
    r"^https?://\S+$",
    r"^(leia|saiba|veja|assista|ouca|acompanhe|acesse)(\s+mais)?\b.*$",
    r"^clique aqui\b.*$",
    r"^abrir no navegador\b.*$",
    r"^open in browser\b.*$",
    r"^compartilhe\b.*$",
    r"^seguir no instagram\b.*$",
    r"^sig[a]?[- ]?nos\b.*$",
    r"^atualize (suas|tus|sus) prefer(encias|encias)\b.*$",
    r"^atualizar (suas|tus|sus) prefer(encias|encias)\b.*$",
    r"^cancele a assinatura\b.*$",
    r"^cancelar a assinatura\b.*$",
    r"^ou cancele a assinatura\b.*$",
    r"^se preferir nao receber\b.*$",
    r"^se preferir não receber\b.*$",
    r"^nao deseja mais receber\b.*$",
    r"^não deseja mais receber\b.*$",
    r"^descadastre[- ]?se\b.*$",
    r"^descadastrar\b.*$",
    r"^gerenciar prefer(encias|encias)\b.*$",
    r"^quer mudar a forma como recebe este? e[- ]?mail\??$",
    r"^atualizar suas preferencias\b.*$",
    r"^atualizar suas preferências\b.*$",
    r"^cancelar inscricao\b.*$",
    r"^cancelar inscrição\b.*$",
    r"^unsubscribe\b.*$",
    r"^view in browser\b.*$",
    r"^nosso e-mail de envio\b.*$",
    r"^nosso email de envio\b.*$",
    r"^copyright\b.*$",
    r"^todos os direitos reservados\b.*$",
    r"^av(enida)?\b.*$",
    r"^s[aã]o paulo\b.*cep\b.*$",
    r"^você recebeu este e-mail\b.*$",
    r"^você pode atualizar suas preferências\b.*$",
    r"^ou deixar de assinar\b.*$",
    r"^obrigad[oa] por ler\b.*$",
    r"^preferencias de e[- ]?mail\b.*$",
    r"^preferencias de email\b.*$",
    r"^esta edicao teve curadoria\b.*$",
]

TRAILING_NOISE_MARKERS = [
    "quer mudar a forma como recebe",
    "atualizar suas preferências",
    "atualize suas preferencias",
    "atualize tus preferencias",
    "atualize sus preferencias",
    "cancele a assinatura",
    "cancelar a assinatura",
    "se preferir nao receber",
    "nao deseja mais receber",
    "descadastre",
    "descadastrar",
    "gerenciar preferencias",
    "unsubscribe",
    "todos os direitos reservados",
    "nosso email de envio",
    "obrigado por ler",
    "preferencias de e-mail",
    "preferencias de email",
    "esta edicao teve curadoria",
]

CTA_PREFIXES = (
    "siga",
    "acompanhe",
    "entre",
    "assine",
    "inscreva",
    "clique",
    "acesse",
    "confira",
    "veja",
    "receba",
    "participe",
    "ouca",
    "escute",
    "atualize",
    "atualizar",
    "cancele",
    "cancelar",
    "descadastre",
    "descadastrar",
    "se preferir",
    "prefira",
    "preferir",
    "gerencie",
    "gerenciar",
)

CTA_MARKERS = (
    "canal",
    "whatsapp",
    "whats",
    "telegram",
    "instagram",
    "youtube",
    "newsletter",
    "podcast",
    "grupo",
    "lista",
    "comunidade",
    "preferencias",
    "assinatura",
    "receber",
    "email",
    "e-mail",
    "emails",
    "descadastro",
)

DATE_LINE_PATTERNS = (
    r"^(?:segunda|terca|quarta|quinta|sexta|sabado|domingo)(?:-feira)?[, ]+\d{1,2}\s+de\s+[a-z]+(?:\s+de\s+\d{4})?\s*$",
    r"^\d{1,2}\s+de\s+[a-z]+(?:\s+de\s+\d{4})?\s*$",
    r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s*$",
)


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize_for_comparison(text: str) -> str:
    text = _strip_accents(text).lower()
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _looks_like_noise(line: str) -> bool:
    if not line:
        return True

    compact = normalize_spaces(line)
    compact_ascii = _strip_accents(compact).lower()

    if len(compact_ascii) < 3:
        return True

    if (
        compact_ascii.count("@") >= 1
        and "." in compact_ascii
        and len(compact_ascii.split()) <= 4
    ):
        return True

    if re.fullmatch(r"[\W_]+", compact):
        return True

    if compact.count("|") >= 3:
        return True

    if _looks_like_call_to_action(compact_ascii):
        return True

    if _looks_like_date_line(compact_ascii):
        return True

    if sum(1 for ch in compact if ch.isdigit()) > len(compact) * 0.45:
        return True

    for pattern in NOISE_PATTERNS:
        if re.match(pattern, compact_ascii, re.IGNORECASE):
            return True

    return False


def _looks_like_call_to_action(line: str) -> bool:
    candidate = normalize_spaces(line)
    if not candidate:
        return False

    compact = _strip_accents(candidate).lower()
    if not any(marker in compact for marker in CTA_MARKERS):
        return False

    return bool(re.match(rf"^({'|'.join(CTA_PREFIXES)})\b", compact))


def _looks_like_date_line(line_ascii: str) -> bool:
    return any(re.match(pattern, line_ascii) for pattern in DATE_LINE_PATTERNS)


def _is_probably_heading(line: str) -> bool:
    candidate = normalize_spaces(line).strip(":- ")
    if not candidate or len(candidate) > 110:
        return False

    if _looks_like_call_to_action(candidate):
        return False

    if _looks_like_noise(candidate):
        return False

    if any(punctuation in candidate for punctuation in (";", "?")):
        return False

    alpha_chars = [ch for ch in candidate if ch.isalpha()]
    if not alpha_chars:
        return False

    uppercase_ratio = sum(1 for ch in alpha_chars if ch.isupper()) / len(alpha_chars)
    sentence_like = candidate.endswith(".")
    word_count = len(candidate.split())
    return (uppercase_ratio > 0.55 or word_count <= 10) and not sentence_like


def _merge_broken_lines(lines: Iterable[str]) -> List[str]:
    merged: List[str] = []

    for raw_line in lines:
        line = normalize_spaces(raw_line)
        if not line:
            continue

        if not merged:
            merged.append(line)
            continue

        previous = merged[-1]
        previous_is_heading = _is_probably_heading(previous)
        if _is_probably_heading(line):
            merged.append(line)
            continue

        previous_ends_sentence = previous.endswith((".", "!", "?", ":"))
        current_starts_lower = line[:1].islower()
        current_is_short_tail = len(line) < 48 and not _is_probably_heading(line)

        if (
            previous_is_heading
            and not current_starts_lower
            and not current_is_short_tail
        ):
            merged.append(line)
            continue

        if not previous_ends_sentence or current_starts_lower or current_is_short_tail:
            merged[-1] = f"{previous} {line}"
        else:
            merged.append(line)

    return merged


def _is_duplicate(candidate: str, seen: List[str]) -> bool:
    normalized_candidate = _normalize_for_comparison(candidate)
    if not normalized_candidate or len(normalized_candidate) < 20:
        return True

    for previous in seen:
        if normalized_candidate == previous:
            return True

        if (
            normalized_candidate in previous
            and len(normalized_candidate) / max(len(previous), 1) > 0.72
        ):
            return True

        if (
            previous in normalized_candidate
            and len(previous) / max(len(normalized_candidate), 1) > 0.72
        ):
            return True

        similarity = SequenceMatcher(None, normalized_candidate, previous).ratio()
        if similarity >= 0.92:
            return True

    return False


def clean_newsletter_text(text: str) -> List[str]:
    text = text or ""
    text = text.replace("\r", "")
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\b\d+\s+de\s+\d+\b", "", text)
    text = re.sub(r"[ \t]+", " ", text)

    lower_text = _strip_accents(text).lower()
    cutoff_index = None
    for marker in TRAILING_NOISE_MARKERS:
        index = lower_text.find(marker)
        if index >= 0:
            cutoff_index = index if cutoff_index is None else min(cutoff_index, index)
    if cutoff_index is not None:
        text = text[:cutoff_index]

    raw_lines = [line for line in text.splitlines()]
    filtered_lines = [line for line in raw_lines if not _looks_like_noise(line)]
    merged_lines = _merge_broken_lines(filtered_lines)

    seen: List[str] = []
    unique_lines: List[str] = []
    for line in merged_lines:
        cleaned = normalize_spaces(line)
        if len(cleaned) < 18 and not _is_probably_heading(cleaned):
            continue
        if _is_duplicate(cleaned, seen):
            continue
        seen.append(_normalize_for_comparison(cleaned))
        unique_lines.append(cleaned)

    return unique_lines


def _text_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _strip_accents(normalize_spaces(text)).lower())


def _heading_candidates(lines: Iterable[str]) -> List[str]:
    candidates: List[str] = []
    for line in lines:
        if not _is_probably_heading(line):
            continue
        candidate = normalize_heading(line)
        if len(candidate.split()) < 3:
            continue
        candidates.append(candidate)

    unique_candidates: List[str] = []
    seen = set()
    for candidate in candidates:
        key = _text_key(candidate)
        if not key or key in seen:
            continue
        seen.add(key)
        unique_candidates.append(candidate)

    return unique_candidates


def _choose_packet_title(subject: str, cleaned_lines: List[str]) -> str:
    subject_title = normalize_heading(subject) or "Newsletter"
    subject_key = _text_key(subject_title)

    for candidate in reversed(_heading_candidates(cleaned_lines)):
        if _text_key(candidate) == subject_key:
            continue

        if ":" in candidate:
            prefix = normalize_heading(candidate.split(":", 1)[0])
            if len(prefix.split()) >= 3:
                return prefix

        return candidate

    if ":" in subject_title:
        prefix = normalize_heading(subject_title.split(":", 1)[0])
        if len(prefix.split()) >= 3:
            return prefix

    return subject_title


def _build_packet_highlights(title: str, cleaned_lines: List[str]) -> List[str]:
    title_key = _text_key(title)
    highlights: List[str] = []

    for line in cleaned_lines:
        candidate = normalize_spaces(line)
        if not candidate:
            continue
        if _text_key(candidate) == title_key:
            continue
        if candidate in highlights:
            continue
        highlights.append(candidate)

    return highlights


def build_source_packets(
    newsletters: List[Dict[str, str]], max_packets: int = 12
) -> List[Dict[str, Any]]:
    packets: List[Dict[str, Any]] = []

    for newsletter in newsletters:
        subject = normalize_spaces(newsletter.get("subject", "").strip())
        sender = normalize_spaces(newsletter.get("sender", "").strip())
        cleaned_lines = clean_newsletter_text(newsletter.get("content", ""))
        if not cleaned_lines:
            continue

        title = _choose_packet_title(subject, cleaned_lines)
        highlights = _build_packet_highlights(title, cleaned_lines)
        if not highlights:
            highlights = cleaned_lines[:2] or [title]

        summary = " ".join(highlights[:2]).strip()
        impact_raw = (
            highlights[2]
            if len(highlights) > 2
            else "Ponto de atenção para investidores."
        )
        impact = impact_raw.lstrip(" ,;:-.")

        packets.append(
            {
                "title": title,
                "sender": sender,
                "highlights": highlights,
                "summary": summary,
                "impact": impact,
            }
        )

        if len(packets) >= max_packets:
            break

    seen_slugs = set()
    for packet in packets:
        title = packet.get("title", "").strip()
        slug = re.sub(r"\W+", "", title).lower()
        if not slug or slug in seen_slugs or len(title) < 5:
            base_title = title or (
                normalize_heading(packet.get("highlights", [""])[0])
                if packet.get("highlights")
                else "Destaque"
            )
            counter = 2
            while slug in seen_slugs:
                title = f"{base_title} ({counter})"
                slug = re.sub(r"\W+", "", title).lower()
                counter += 1

        packet["title"] = title
        seen_slugs.add(slug)

    return packets


def render_prompt_payload(
    source_packets: List[Dict[str, Any]], max_chars: int = 18000
) -> str:
    rendered_packets: List[str] = []
    current_chars = 0

    for index, packet in enumerate(source_packets, start=1):
        title = packet.get("title", "Newsletter")
        sender = packet.get("sender", "")
        highlights = packet.get("highlights", [])

        lines = [f"[Fonte {index}] {title}"]
        if sender:
            lines.append(f"Remetente: {sender}")
        for highlight in highlights:
            lines.append(f"- {highlight}")

        block = "\n".join(lines)
        if current_chars + len(block) > max_chars and rendered_packets:
            break
        rendered_packets.append(block)
        current_chars += len(block)

    return "\n\n".join(rendered_packets).strip()
