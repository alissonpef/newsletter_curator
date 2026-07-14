from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF

from hermes.core.digest_document import normalize_heading, normalize_spaces
from hermes.core.interfaces import PdfPort

FONT_DIR_CANDIDATES = (
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/dejavu"),
)


class HermesPdf(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font("HermesSans", "", 8)
        self.set_text_color(104, 111, 121)
        self.cell(0, 6, f"Hermes · Página {self.page_no()}", align="C")


class FpdfAdapter(PdfPort):
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_font_dir(self) -> Path:
        for candidate in FONT_DIR_CANDIDATES:
            if (candidate / "DejaVuSans.ttf").exists() and (candidate / "DejaVuSerif.ttf").exists():
                return candidate
        raise FileNotFoundError("DejaVu fonts not found in the expected Linux font directories.")

    def _build_pdf(self) -> HermesPdf:
        pdf = HermesPdf(format="A4")
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.set_margins(16, 16, 16)
        font_dir = self._resolve_font_dir()
        pdf.add_font("HermesSans", "", str(font_dir / "DejaVuSans.ttf"))
        pdf.add_font("HermesSans", "B", str(font_dir / "DejaVuSans-Bold.ttf"))
        pdf.add_font("HermesSerif", "", str(font_dir / "DejaVuSerif.ttf"))
        pdf.add_font("HermesSerif", "B", str(font_dir / "DejaVuSerif-Bold.ttf"))
        pdf.add_page()
        return pdf

    def _safe_text(self, value: Any) -> str:
        return normalize_spaces(str(value or ""))

    def _draw_cover(self, pdf: HermesPdf, date_ref: str, source_count: int) -> None:
        page_width = pdf.w - pdf.l_margin - pdf.r_margin
        start_x = pdf.l_margin
        start_y = pdf.get_y()

        pdf.set_fill_color(247, 240, 229)
        pdf.rect(start_x, start_y, page_width, 34, style="F")
        pdf.set_fill_color(20, 33, 52)
        pdf.rect(start_x + page_width - 62, start_y, 62, 34, style="F")

        pdf.set_xy(start_x + 6, start_y + 6)
        pdf.set_font("HermesSans", "B", 9)
        pdf.set_text_color(132, 97, 48)
        pdf.cell(0, 5, "Briefing Executivo")

        pdf.set_xy(start_x + 6, start_y + 13)
        pdf.set_font("HermesSerif", "B", 24)
        pdf.set_text_color(20, 33, 52)
        pdf.cell(0, 8, "Hermes")

        pdf.set_xy(start_x + 6, start_y + 23)
        pdf.set_font("HermesSans", "", 10)
        pdf.set_text_color(79, 86, 96)
        pdf.cell(0, 5, f"Edição de {date_ref} · {source_count} fontes consolidadas")

        pdf.set_xy(start_x + page_width - 56, start_y + 9)
        pdf.set_font("HermesSans", "B", 10)
        pdf.set_text_color(255, 255, 255)
        pdf.multi_cell(
            46,
            5,
            "Leitura limpa, sem ruído e pronta para PDF, áudio e Kindle.",
            align="L",
        )

        pdf.set_y(start_y + 42)

    def _section_label(self, pdf: HermesPdf, text: str) -> None:
        pdf.set_font("HermesSans", "B", 9)
        pdf.set_text_color(132, 97, 48)
        pdf.cell(0, 5, self._safe_text(text))
        pdf.ln(5)
        pdf.set_draw_color(226, 217, 203)
        pdf.line(pdf.l_margin, pdf.get_y() + 1, pdf.w - pdf.r_margin, pdf.get_y() + 1)
        pdf.ln(5)

    def _paragraph(
        self, pdf: HermesPdf, text: str, font_size: int = 12, serif: bool = False
    ) -> None:
        content = self._safe_text(text)
        if not content:
            return
        pdf.set_font("HermesSerif" if serif else "HermesSans", "", font_size)
        pdf.set_text_color(35, 39, 47)
        pdf.multi_cell(0, 6.5 if font_size <= 12 else 7.2, content)
        pdf.ln(2)

    def _count_wrapped_lines(
        self,
        pdf: HermesPdf,
        text: str,
        width: float,
        font_family: str,
        style: str,
        font_size: float,
    ) -> int:
        content = self._safe_text(text)
        if not content:
            return 0

        pdf.set_font(font_family, style, font_size)
        total_lines = 0

        for paragraph in content.split("\n"):
            paragraph = paragraph.strip()
            if not paragraph:
                total_lines += 1
                continue

            current = ""
            for word in paragraph.split():
                candidate = f"{current} {word}".strip()
                if pdf.get_string_width(candidate) <= width:
                    current = candidate
                    continue

                if current:
                    total_lines += 1

                if pdf.get_string_width(word) <= width:
                    current = word
                    continue

                chunk = ""
                for char in word:
                    chunk_candidate = f"{chunk}{char}"
                    if pdf.get_string_width(chunk_candidate) <= width:
                        chunk = chunk_candidate
                    else:
                        if chunk:
                            total_lines += 1
                        chunk = char
                current = chunk

            if current:
                total_lines += 1

        return max(1, total_lines)

    def _topic_card_metrics(
        self, pdf: HermesPdf, width: float, title: str, summary: str, impact: str
    ) -> dict[str, float]:
        title_width = width - 48
        body_width = width - 12

        title_lines = self._count_wrapped_lines(pdf, title, title_width, "HermesSerif", "B", 13)
        summary_lines = (
            self._count_wrapped_lines(pdf, summary, body_width, "HermesSans", "", 9.5)
            if summary
            else 0
        )
        impact_lines = (
            self._count_wrapped_lines(pdf, impact, body_width, "HermesSans", "", 8.5)
            if impact
            else 0
        )

        title_top = 4.5
        title_height = title_lines * 6.0
        title_bottom = title_top + title_height

        if summary_lines:
            summary_top = max(15.0, title_bottom + 3.0)
            summary_height = summary_lines * 5.0
            impact_top = summary_top + summary_height + 3.0
        else:
            summary_top = title_bottom + 3.0
            summary_height = 0.0
            impact_top = summary_top

        impact_height = impact_lines * 4.2
        total_height = impact_top + impact_height + 8.0

        return {
            "height": max(24.0, total_height),
            "title_top": title_top,
            "summary_top": summary_top,
            "impact_top": impact_top,
        }

    def _thesis_card(self, pdf: HermesPdf, thesis: str, executive_summary: str) -> None:
        start_x = pdf.l_margin
        start_y = pdf.get_y()
        width = pdf.w - pdf.l_margin - pdf.r_margin
        thesis_lines = max(2, len(self._safe_text(thesis)) // 52 + 1)
        summary_lines = max(2, len(self._safe_text(executive_summary)) // 68 + 1)
        box_height = 18 + thesis_lines * 6.5 + summary_lines * 5.2

        pdf.set_fill_color(243, 248, 245)
        pdf.set_draw_color(196, 220, 209)
        pdf.rect(start_x, start_y, width, box_height, style="DF")

        pdf.set_xy(start_x + 6, start_y + 6)
        pdf.set_font("HermesSans", "B", 9)
        pdf.set_text_color(42, 91, 71)
        pdf.cell(0, 5, "Tese do dia")
        pdf.ln(5)

        pdf.set_x(start_x + 6)
        pdf.ln(2)
        pdf.set_font("HermesSerif", "B", 14)
        pdf.set_text_color(20, 33, 52)
        pdf.multi_cell(
            width - 12,
            6.5,
            self._safe_text(thesis) or "Sem tese consolidada para esta edição.",
        )

        if self._safe_text(thesis) != self._safe_text(executive_summary):
            pdf.ln(2)
            pdf.set_x(start_x + 6)
            pdf.set_font("HermesSans", "", 10)
            pdf.set_text_color(79, 86, 96)
            pdf.multi_cell(width - 12, 5, self._safe_text(executive_summary))

        pdf.set_y(start_y + box_height + 6)

    def _market_cards(self, pdf: HermesPdf, market_data: dict[str, dict[str, str]]) -> None:
        self._section_label(pdf, "Radar de Mercado")
        cards = list(market_data.items())
        if not cards:
            self._paragraph(pdf, "Sem dados de mercado disponíveis nesta execução.", font_size=10)
            return

        page_width = pdf.w - pdf.l_margin - pdf.r_margin
        gap = 6
        col_width = (page_width - gap) / 2

        for row_start in range(0, len(cards), 2):
            row_y = pdf.get_y()
            row = cards[row_start : row_start + 2]

            for column, (name, payload) in enumerate(row):
                x = pdf.l_margin + column * (col_width + gap)
                pdf.set_xy(x, row_y)
                pdf.set_fill_color(251, 248, 242)
                pdf.set_draw_color(228, 221, 211)
                pdf.rect(x, row_y, col_width, 18, style="DF")

                pdf.set_xy(x + 5, row_y + 4)
                pdf.set_font("HermesSans", "B", 10)
                pdf.set_text_color(20, 33, 52)
                pdf.cell(col_width - 10, 4, self._safe_text(name))

                pdf.set_xy(x + 5, row_y + 9)
                pdf.set_font("HermesSans", "", 11)
                direction = payload.get("direction", "flat")
                if direction == "up":
                    pdf.set_text_color(42, 126, 82)
                elif direction == "down":
                    pdf.set_text_color(179, 71, 62)
                else:
                    pdf.set_text_color(90, 96, 107)
                pdf.cell(
                    col_width - 10,
                    5,
                    self._safe_text(payload.get("display") or payload.get("value")),
                )

            pdf.set_y(row_y + 22)

    def _bullet_list(self, pdf: HermesPdf, title: str, items: list[str]) -> None:
        filtered = [self._safe_text(item) for item in items if self._safe_text(item)]
        if not filtered:
            return

        self._section_label(pdf, title)
        for item in filtered:
            bullet_y = pdf.get_y() + 1.5
            pdf.set_fill_color(42, 91, 71)
            pdf.ellipse(pdf.l_margin, bullet_y, 2, 2, style="F")
            pdf.set_x(pdf.l_margin + 6)
            pdf.set_font("HermesSans", "", 11)
            pdf.set_text_color(35, 39, 47)
            pdf.multi_cell(0, 6, item)
            pdf.ln(1)

    def _topic_cards(self, pdf: HermesPdf, topics: list[dict[str, str]]) -> None:
        cleaned_topics = [topic for topic in topics if topic]
        if not cleaned_topics:
            return

        self._section_label(pdf, "Temas em Foco")
        for index, topic in enumerate(cleaned_topics, start=1):
            start_x = pdf.l_margin
            start_y = pdf.get_y()
            width = pdf.w - pdf.l_margin - pdf.r_margin
            title = normalize_heading(topic.get("title", "")) or "Tema"
            summary = self._safe_text(topic.get("summary", ""))
            impact_raw = self._safe_text(topic.get("impact", ""))

            if impact_raw.lower() in {
                "",
                "ponto de atenção para investidores.",
                "ponto de atencao para investidores",
            }:
                impact = ""
            else:
                impact = impact_raw
            metrics = self._topic_card_metrics(pdf, width, title, summary, impact)

            if pdf.get_y() + metrics["height"] > pdf.h - pdf.b_margin:
                pdf.add_page()
                start_y = pdf.get_y()

            pdf.set_fill_color(255, 255, 255)
            pdf.set_draw_color(225, 218, 208)
            pdf.rect(start_x, start_y, width, metrics["height"], style="DF")

            pdf.set_xy(start_x + 5, start_y + 5)
            pdf.set_font("HermesSans", "B", 9)
            pdf.set_text_color(132, 97, 48)
            pdf.cell(10, 5, f"{index:02d}")

            pdf.set_xy(start_x + 16, start_y + metrics["title_top"])
            pdf.set_font("HermesSerif", "B", 13)
            pdf.set_text_color(20, 33, 52)
            pdf.multi_cell(width - 48, 6, title)

            signal = self._safe_text(topic.get("signal", "Média"))
            badge_x = start_x + width - 28
            badge_y = start_y + 4.5
            if signal == "Alta":
                pdf.set_fill_color(235, 247, 239)
                pdf.set_text_color(42, 126, 82)
            elif signal == "Baixa":
                pdf.set_fill_color(13, 17, 23)
                pdf.set_text_color(255, 255, 255)
            else:
                pdf.set_fill_color(243, 240, 255)
                pdf.set_text_color(90, 77, 149)
            pdf.rect(badge_x, badge_y, 22, 7, style="F")
            pdf.set_xy(badge_x, badge_y + 1.2)
            pdf.set_font("HermesSans", "B", 8)
            pdf.cell(22, 4, signal, align="C")

            pdf.set_xy(start_x + 6, start_y + metrics["summary_top"])
            pdf.set_font("HermesSans", "", 9.5)
            pdf.set_text_color(60, 68, 80)
            if summary:
                pdf.multi_cell(width - 12, 5.0, summary)

            pdf.set_xy(start_x + 6, start_y + metrics["impact_top"])
            if impact:
                pdf.set_font("HermesSans", "", 8.5)
                pdf.set_text_color(79, 86, 96)
                pdf.multi_cell(width - 12, 4.2, impact)

            final_y = max(pdf.get_y(), start_y + metrics["height"])
            pdf.set_y(final_y + 4)

    def render_pdf(self, date_ref: str, digest: dict[str, Any], market_data: dict[str, Any]) -> str:
        pdf = self._build_pdf()

        summary_data = digest.get("summaryData") or {}
        thesis = summary_data.get("thesis") or digest.get("summary") or ""
        executive_summary = summary_data.get("executiveSummary") or digest.get("summary") or ""
        key_points = summary_data.get("keyPoints") or []
        topics = summary_data.get("topics") or []
        closing = summary_data.get("closing") or ""
        source_count = summary_data.get("sourceCount") or digest.get("sourceCount") or 0

        self._draw_cover(pdf, date_ref, source_count)
        self._market_cards(pdf, market_data or {})
        self._thesis_card(pdf, thesis, executive_summary)
        self._bullet_list(pdf, "Leituras Prioritárias", key_points)
        self._topic_cards(pdf, topics)

        if closing:
            self._section_label(pdf, "Fechamento")
            self._paragraph(pdf, closing, serif=True)

        date_obj = datetime.strptime(date_ref, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%d_%m_%Y")
        pdf_filename = f"Briefing_Hermes_{formatted_date}.pdf"
        pdf_path = self.output_dir / pdf_filename
        pdf.output(str(pdf_path))
        return str(pdf_path)
