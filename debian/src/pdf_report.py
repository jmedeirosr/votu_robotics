"""Professional PDF reports for processed field maps, powered by ReportLab."""

from __future__ import annotations

from datetime import datetime
from math import ceil
from pathlib import Path

import pandas as pd
from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)
MARGIN = 28.0
FOOTER_HEIGHT = 38.0
TABLE_BOTTOM = MARGIN + FOOTER_HEIGHT
TABLE_HEADER_HEIGHT = 23.0
MINIMUM_ROW_HEIGHT = 24.0

INK = HexColor("#0f172a")
MUTED = HexColor("#64748b")
ACCENT = HexColor("#176b4d")
ACCENT_DARK = HexColor("#10543b")
AMBER = HexColor("#f6b73c")
BORDER = HexColor("#dbe5df")
SURFACE = HexColor("#f8fafc")
ROW_ODD = HexColor("#f5faf3")
ROW_EVEN = HexColor("#eaf5e6")
HEADER_FILL = HexColor("#d8edcf")
GRID = HexColor("#d4e5ce")


def _text(value) -> str:
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _matrix_value(df, row: int, column: int) -> str:
    if df is None:
        return ""
    try:
        return _text(df.iloc[row, column])
    except (IndexError, KeyError):
        return ""


def _unique_count(df) -> int:
    if df is None:
        return 0
    values = pd.Series(df.to_numpy().ravel()).dropna()
    values = values[values.astype(str).str.strip() != ""]
    return int(values.nunique())


def _fit_text(text: str, font_name: str, font_size: float, max_width: float) -> str:
    text = str(text)
    if stringWidth(text, font_name, font_size) <= max_width:
        return text
    suffix = "..."
    available = max(0.0, max_width - stringWidth(suffix, font_name, font_size))
    while text and stringWidth(text, font_name, font_size) > available:
        text = text[:-1]
    return text.rstrip() + suffix


def _draw_logo(pdf: canvas.Canvas, logo_path: Path, x: float, y: float, width: float, height: float) -> None:
    if logo_path.exists():
        try:
            image = ImageReader(str(logo_path))
            source_width, source_height = image.getSize()
            scale = min(width / source_width, height / source_height)
            drawn_width = source_width * scale
            drawn_height = source_height * scale
            pdf.drawImage(
                image,
                x,
                y + ((height - drawn_height) / 2),
                width=drawn_width,
                height=drawn_height,
                preserveAspectRatio=True,
                mask="auto",
            )
            return
        except Exception:
            pass

    pdf.setFillColor(ACCENT)
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(x, y + 10, "VOTU")


def _draw_header(
    pdf: canvas.Canvas,
    saved: dict,
    logo_path: Path,
    page_number: int,
    page_count: int,
    generated_at: datetime,
) -> float:
    top = PAGE_HEIGHT - MARGIN
    _draw_logo(pdf, logo_path, MARGIN, top - 42, 150, 38)

    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawRightString(PAGE_WIDTH - MARGIN, top - 14, "Relatório de mapa processado")
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 7.5)
    generated = generated_at.strftime("%d/%m/%Y às %H:%M")
    pdf.drawRightString(
        PAGE_WIDTH - MARGIN,
        top - 31,
        f"Gerado em {generated}  |  Página {page_number} de {page_count}",
    )

    line_y = top - 50
    pdf.setStrokeColor(ACCENT)
    pdf.setLineWidth(2.2)
    pdf.line(MARGIN, line_y, PAGE_WIDTH - MARGIN, line_y)

    if page_number == 1:
        return line_y - 13

    title = f"{saved['book_name']}  |  {saved['entry']}"
    if saved.get("tier") is not None:
        title += f"  |  Tier {saved['tier']}"
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(MARGIN, line_y - 19, _fit_text(title, "Helvetica-Bold", 10, PAGE_WIDTH - (2 * MARGIN)))
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 7.5)
    pdf.drawString(MARGIN, line_y - 33, "Continuação do mapa de campo")
    return line_y - 45


def _active_cells(df: pd.DataFrame) -> int:
    count = int(df.notna().to_numpy().sum())
    try:
        count -= int((df == 0).to_numpy().sum())
    except (TypeError, ValueError):
        pass
    return max(count, 0)


def _draw_summary(pdf: canvas.Canvas, y_top: float, saved: dict) -> float:
    fields = [
        ("LOCAL", _text(saved.get("book_name"))),
        ("ENSAIO", _text(saved.get("entry"))),
        ("TIER", _text(saved.get("tier")) or "Não informado"),
        ("PARCELAS", str(_active_cells(saved["result"]))),
        ("RANGES", str(_unique_count(saved.get("range_matrix")))),
        ("PLOTS", str(_unique_count(saved.get("plot_matrix")))),
    ]
    gap = 7.0
    available_width = PAGE_WIDTH - (2 * MARGIN)
    card_width = (available_width - (gap * (len(fields) - 1))) / len(fields)
    card_height = 45.0
    card_y = y_top - card_height

    for index, (label, value) in enumerate(fields):
        x = MARGIN + (index * (card_width + gap))
        pdf.setFillColor(SURFACE)
        pdf.setStrokeColor(BORDER)
        pdf.setLineWidth(0.7)
        pdf.roundRect(x, card_y, card_width, card_height, 6, fill=1, stroke=1)
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica-Bold", 6.5)
        pdf.drawString(x + 8, card_y + 29, label)
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(x + 8, card_y + 12, _fit_text(value, "Helvetica-Bold", 9, card_width - 16))

    return card_y - 13


def _draw_map_title(
    pdf: canvas.Canvas,
    y_top: float,
    start_row: int,
    end_row: int,
    total_rows: int,
) -> float:
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 10.5)
    pdf.drawString(MARGIN, y_top - 10, "Mapa de campo")
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 7.5)
    pdf.drawRightString(
        PAGE_WIDTH - MARGIN,
        y_top - 10,
        f"Linhas {start_row + 1}-{end_row} de {total_rows}",
    )
    return y_top - 21


def _draw_centered_text(
    pdf: canvas.Canvas,
    value: str,
    x: float,
    baseline: float,
    width: float,
    font_name: str,
    font_size: float,
    color: Color,
) -> None:
    pdf.setFillColor(color)
    pdf.setFont(font_name, font_size)
    fitted = _fit_text(value, font_name, font_size, max(1, width - 5))
    pdf.drawCentredString(x + (width / 2), baseline, fitted)


def _draw_map(
    pdf: canvas.Canvas,
    table_top: float,
    saved: dict,
    start_row: int,
    end_row: int,
) -> None:
    df = saved["result"]
    range_df = saved.get("range_matrix")
    plot_df = saved.get("plot_matrix")
    columns = list(df.columns)
    visible_rows = end_row - start_row
    if visible_rows <= 0 or not columns:
        return

    table_width = PAGE_WIDTH - (2 * MARGIN)
    table_height = table_top - TABLE_BOTTOM
    index_width = min(42.0, table_width * 0.07)
    cell_width = (table_width - index_width) / len(columns)
    row_height = (table_height - TABLE_HEADER_HEIGHT) / visible_rows
    table_x = MARGIN

    pdf.setFillColor(HEADER_FILL)
    pdf.setStrokeColor(HexColor("#8db482"))
    pdf.setLineWidth(0.8)
    pdf.roundRect(table_x, TABLE_BOTTOM, table_width, table_height, 6, fill=1, stroke=1)
    pdf.setFillColor(HEADER_FILL)
    pdf.rect(
        table_x,
        table_top - TABLE_HEADER_HEIGHT,
        table_width,
        TABLE_HEADER_HEIGHT,
        fill=1,
        stroke=0,
    )

    header_font = max(5.2, min(7.5, cell_width / 8.5))
    _draw_centered_text(
        pdf,
        "Índice",
        table_x,
        table_top - TABLE_HEADER_HEIGHT + 8,
        index_width,
        "Helvetica-Bold",
        6.5,
        INK,
    )
    for column_index, column in enumerate(columns):
        x = table_x + index_width + (column_index * cell_width)
        _draw_centered_text(
            pdf,
            _text(column),
            x,
            table_top - TABLE_HEADER_HEIGHT + 8,
            cell_width,
            "Helvetica-Bold",
            header_font,
            INK,
        )

    total_rows = len(df.index)
    detail_font = max(4.6, min(6.2, cell_width / 11, row_height / 5))
    entry_font = max(5.5, min(8.5, cell_width / 7, row_height / 3.5))
    data_top = table_top - TABLE_HEADER_HEIGHT

    for visible_index, row_index in enumerate(range(start_row, end_row)):
        row_top = data_top - (visible_index * row_height)
        row_bottom = row_top - row_height
        pdf.setFillColor(ROW_ODD if visible_index % 2 == 0 else ROW_EVEN)
        pdf.rect(table_x, row_bottom, table_width, row_height, fill=1, stroke=0)
        pdf.setStrokeColor(GRID)
        pdf.setLineWidth(0.45)
        pdf.line(table_x, row_bottom, table_x + table_width, row_bottom)

        _draw_centered_text(
            pdf,
            str(total_rows - row_index),
            table_x,
            row_bottom + (row_height / 2) - 2.5,
            index_width,
            "Helvetica-Bold",
            max(5.5, detail_font),
            INK,
        )

        for column_index in range(len(columns)):
            x = table_x + index_width + (column_index * cell_width)
            pdf.line(x, row_bottom, x, row_top)
            entry = _matrix_value(df, row_index, column_index)
            plot = _matrix_value(plot_df, row_index, column_index)
            range_value = _matrix_value(range_df, row_index, column_index)

            if plot:
                _draw_centered_text(
                    pdf,
                    f"P {plot}",
                    x,
                    row_top - detail_font - 2.5,
                    cell_width,
                    "Helvetica",
                    detail_font,
                    MUTED,
                )
            _draw_centered_text(
                pdf,
                entry,
                x,
                row_bottom + (row_height / 2) - (entry_font / 3),
                cell_width,
                "Helvetica-Bold",
                entry_font,
                INK,
            )
            if range_value:
                _draw_centered_text(
                    pdf,
                    f"R {range_value}",
                    x,
                    row_bottom + 3,
                    cell_width,
                    "Helvetica-Bold",
                    detail_font,
                    ACCENT,
                )

    pdf.setStrokeColor(HexColor("#7ea873"))
    pdf.setLineWidth(1.1)
    pdf.line(table_x + index_width, TABLE_BOTTOM, table_x + index_width, table_top)


def _draw_footer(pdf: canvas.Canvas) -> None:
    line_y = MARGIN + 25
    pdf.setStrokeColor(BORDER)
    pdf.setLineWidth(0.6)
    pdf.line(MARGIN, line_y, PAGE_WIDTH - MARGIN, line_y)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 6.7)
    pdf.drawString(MARGIN, line_y - 13, "P = Plot  |  R = Range  |  Valor central = Entry")
    pdf.setFillColor(ACCENT)
    pdf.setFont("Helvetica-Bold", 6.7)
    pdf.drawRightString(PAGE_WIDTH - MARGIN, line_y - 13, "VOTU FieldOps")


def _page_capacities() -> tuple[int, int]:
    first_table_top = PAGE_HEIGHT - MARGIN - 50 - 13 - 45 - 13 - 21
    next_table_top = PAGE_HEIGHT - MARGIN - 50 - 45 - 21
    first_capacity = max(
        1,
        int((first_table_top - TABLE_BOTTOM - TABLE_HEADER_HEIGHT) / MINIMUM_ROW_HEIGHT),
    )
    next_capacity = max(
        1,
        int((next_table_top - TABLE_BOTTOM - TABLE_HEADER_HEIGHT) / MINIMUM_ROW_HEIGHT),
    )
    return first_capacity, next_capacity


def generate_map_report(saved: dict, output_path: Path, logo_path: Path) -> Path:
    """Generate one polished PDF report for one processed map."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total_rows = len(saved["result"].index)
    if total_rows == 0 or len(saved["result"].columns) == 0:
        raise ValueError("O mapa processado não possui células para exportação.")

    first_capacity, next_capacity = _page_capacities()
    remaining_rows = max(0, total_rows - first_capacity)
    page_count = 1 + (ceil(remaining_rows / next_capacity) if remaining_rows else 0)
    generated_at = datetime.now()

    pdf = canvas.Canvas(
        str(output_path),
        pagesize=landscape(A4),
        pageCompression=1,
    )
    pdf.setTitle(f"Mapa processado - {saved['book_name']} - {saved['entry']}")
    pdf.setAuthor("VOTU FieldOps")
    pdf.setCreator("VOTU FieldOps - ReportLab")
    pdf.setSubject("Relatório de mapa de campo processado")

    start_row = 0
    for page_number in range(1, page_count + 1):
        pdf.setFillColor(white)
        pdf.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)
        content_top = _draw_header(
            pdf,
            saved,
            Path(logo_path),
            page_number,
            page_count,
            generated_at,
        )
        if page_number == 1:
            content_top = _draw_summary(pdf, content_top, saved)

        capacity = first_capacity if page_number == 1 else next_capacity
        end_row = min(total_rows, start_row + capacity)
        table_top = _draw_map_title(pdf, content_top, start_row, end_row, total_rows)
        _draw_map(pdf, table_top, saved, start_row, end_row)
        _draw_footer(pdf)
        start_row = end_row
        if page_number < page_count:
            pdf.showPage()

    pdf.save()
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("O arquivo PDF não foi criado corretamente.")
    return output_path
