import sys
import time
from pathlib import Path

import pandas as pd

from PyQt6.QtCore import QEasingCurve, QObject, QPointF, QRectF, QSize, Qt, QThread, QTimer, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QLinearGradient, QMovie, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplashScreen,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from matrix_map import main
from pdf_report import generate_map_report
from serial_commands import booknames_list
from serial_commands import entries_list
from serial_commands import get_tier_column
from serial_commands import logger
from serial_commands import read_data_from_excel
from serial_commands import send_serial
from serial_commands import tiers_list


try:
    import qtawesome as qta
except ImportError:
    qta = None

DEFAULT_TEXT = "Por favor, faça o upload da planilha."
BUTTON_TEXT = "Carregar planilha"
MATRIX_TEXT = "Gerar mapa"
NUM_PASSES_TEXT = "Parcelas"
BOOK_NAMES_TEXT = "Local"
ENTRY_TEXT = "Ensaio"
TIER_TEXT = "Tier"
START_FROM_TEXT = "Iniciar a partir de:"

PROCESS_DELAY_SECONDS = 0

BG_COLOR = "#f5f7fb"
PANEL_COLOR = "#ffffff"
SIDEBAR_COLOR = "#f8fafc"
BORDER_COLOR = "#e2e8f0"
TEXT_COLOR = "#0f172a"
MUTED_COLOR = "#64748b"
ACCENT_COLOR = "#176b4d"
ACCENT_HOVER = "#10543b"
BLUE_COLOR = "#f6b73c"
BLUE_HOVER = "#e99f16"
RED_COLOR = "#b73535"
RED_HOVER = "#922929"
FIELD_BG = "#eef7ec"
FIELD_ROW_ODD = "#f4fbf1"
FIELD_ROW_EVEN = "#e4f2df"
FIELD_ACTIVE = "#bce5ca"
FIELD_HEADER = "#d8edcf"
SURFACE_ALT = "#f8fafc"
INK_SOFT = "#334155"
CHART_BLUE = "#2563eb"
CHART_TEAL = "#0f9f8f"
CHART_AMBER = "#f59e0b"
CHART_PURPLE = "#7c3aed"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_PATH = PROJECT_ROOT / "assets"

MAP_EXPORTS_PATH = PROJECT_ROOT /"mapas"

LOGO_PATH = ASSETS_PATH / "logo-long.png"
ICON_PATH = ASSETS_PATH / "logo-icon.ico"
TRACTOR_GIF_PATH = ASSETS_PATH / "tractor.gif"
ICON_ASSETS_PATH = ASSETS_PATH


def to_list(values):
    return [str(value) for value in values]


class Card(QFrame):
    def __init__(self, object_name="Card", parent=None):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setFrameShape(QFrame.Shape.NoFrame)


class ProcessedCard(Card):
    def __init__(self, parent=None):
        super().__init__("ProcessedCard", parent)
        self.hover_progress = 0.0
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMinimumHeight(86)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setColor(QColor(15, 23, 42, 0))
        self.shadow.setBlurRadius(0)
        self.shadow.setOffset(0, 0)
        self.setGraphicsEffect(self.shadow)

        self.hover_animation = QVariantAnimation(self)
        self.hover_animation.setDuration(160)
        self.hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.hover_animation.valueChanged.connect(self.set_hover_progress)
        self.update_hover_style()

    def enterEvent(self, event):
        self.animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.animate_hover(0.0)
        super().leaveEvent(event)

    def animate_hover(self, target):
        self.hover_animation.stop()
        self.hover_animation.setStartValue(self.hover_progress)
        self.hover_animation.setEndValue(target)
        self.hover_animation.start()

    def set_hover_progress(self, value):
        self.hover_progress = float(value)
        self.update_hover_style()

    def blend_color(self, start, end):
        start_color = QColor(start)
        end_color = QColor(end)
        amount = self.hover_progress
        return QColor(
            round(start_color.red() + ((end_color.red() - start_color.red()) * amount)),
            round(start_color.green() + ((end_color.green() - start_color.green()) * amount)),
            round(start_color.blue() + ((end_color.blue() - start_color.blue()) * amount)),
        ).name()

    def update_hover_style(self):
        background = self.blend_color("#ffffff", "#fbfffc")
        border = self.blend_color("#e2e8f0", "#b7d6c4")
        self.shadow.setColor(QColor(15, 23, 42, round(34 * self.hover_progress)))
        self.shadow.setBlurRadius(2 + (18 * self.hover_progress))
        self.shadow.setOffset(0, 1 + (4 * self.hover_progress))
        self.setStyleSheet(
            f"""
            QFrame#ProcessedCard {{
                background: {background};
                border: 1px solid {border};
                border-radius: 16px;
            }}
            QLabel {{ background: transparent; }}
            QPushButton#ProcessedViewButton {{
                background: {ACCENT_COLOR};
                color: white;
                border: 0;
                border-radius: 16px;
                min-width: 32px;
                max-width: 32px;
                min-height: 32px;
                max-height: 32px;
                font-family: "Segoe UI";
                font-size: 14px;
                font-weight: 700;
            }}
            QPushButton#ProcessedViewButton:hover {{
                background: {ACCENT_HOVER};
            }}
            """
        )


class IconLabel(QWidget):
    def __init__(self, text, icon=None, parent=None):
        super().__init__(parent)
        self.setObjectName("IconLabel")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        if icon is not None and not icon.isNull():
            icon_label = QLabel()
            icon_label.setObjectName("InlineIcon")
            icon_label.setPixmap(icon.pixmap(18, 18))
            layout.addWidget(icon_label)

        text_label = QLabel(text)
        text_label.setObjectName("FieldLabel")
        layout.addWidget(text_label)
        layout.addStretch(1)


class MapWidget(QWidget):
    resized = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.df = None
        self.range_df = None
        self.plot_df = None
        self.row_labels = []
        self.cell_positions = {}
        self.active_cell = None
        self.actuator_current_pos = None
        self.actuator_target_pos = None
        self.actuator_previous_pos = None
        self.actuator_progress = 1.0
        self.actuator_phase = 0
        self.actuator_timer = QTimer(self)
        self.actuator_timer.setInterval(45)
        self.actuator_timer.timeout.connect(self.advance_actuator)
        self.setMinimumHeight(420)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def sizeHint(self):
        return QSize(980, max(self.minimumHeight(), 420))

    def advance_actuator(self):
        self.actuator_phase = (self.actuator_phase + 1) % 24
        if self.actuator_target_pos is not None:
            self.actuator_progress = min(1.0, self.actuator_progress + 0.055)
            if self.actuator_previous_pos is None:
                self.actuator_current_pos = self.actuator_target_pos
            else:
                eased = 1 - ((1 - self.actuator_progress) ** 3)
                self.actuator_current_pos = QPointF(
                    self.actuator_previous_pos.x()
                    + ((self.actuator_target_pos.x() - self.actuator_previous_pos.x()) * eased),
                    self.actuator_previous_pos.y()
                    + ((self.actuator_target_pos.y() - self.actuator_previous_pos.y()) * eased),
                )
        if self.active_cell is not None or self.actuator_current_pos is not None:
            self.update()

    def set_data(self, df, range_df, plot_df, row_labels):
        self.df = df
        self.range_df = range_df
        self.plot_df = plot_df
        self.row_labels = row_labels
        self.active_cell = None
        row_count = len(df.index) if df is not None else 0
        column_count = len(df.columns) if df is not None else 0
        self.setMinimumHeight(max(420, 18 + 36 + (row_count * 48) + 18))
        self.setMinimumWidth(max(860, 18 + 70 + (column_count * 76) + 18))
        self.updateGeometry()
        self.update()

    def clear(self):
        self.df = None
        self.range_df = None
        self.plot_df = None
        self.row_labels = []
        self.cell_positions = {}
        self.active_cell = None
        self.actuator_current_pos = None
        self.actuator_target_pos = None
        self.actuator_previous_pos = None
        self.actuator_progress = 1.0
        
        self.setMinimumHeight(420)
        self.setMinimumWidth(860)
        self.updateGeometry()
        self.update()

    def show_tractor_at_cell(self, row_index, column_index):
        self.active_cell = (row_index, column_index)
        rect = self.cell_positions.get(self.active_cell)
        
        if rect is not None:
            target = QPointF(rect.left() + 24, rect.center().y())
            self.actuator_previous_pos = self.actuator_current_pos or target
            self.actuator_target_pos = target
            self.actuator_progress = 0.0
        
        if not self.actuator_timer.isActive():
            self.actuator_timer.start()
        self.update()

    def hide_tractor(self):
        self.active_cell = None
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resized.emit()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        background = QLinearGradient(0, 0, self.width(), self.height())
        background.setColorAt(0, QColor("#f2f8ef"))
        background.setColorAt(1, QColor("#e3f1df"))
        painter.fillRect(self.rect(), background)

        if self.df is None:
            self.draw_empty_state(painter)
            return

        columns = list(self.df.columns)
        row_count = len(self.df.index)
        column_count = len(columns)
        if row_count == 0 or column_count == 0:
            self.draw_empty_state(painter)
            return

        margin = 18
        header_height = 36
        index_width = 70
        cell_height = 48

        available_width = max(self.width() - (margin * 2) - index_width, column_count)
        cell_width = available_width / column_count
        table_width = index_width + available_width
        table_height = header_height + (row_count * cell_height)
        x0 = margin
        y0 = margin
        self.cell_positions = {}

        painter.setPen(QPen(QColor("#94bd8b"), 1))
        painter.setBrush(QColor("#eaf6e4"))
        painter.drawRoundedRect(QRectF(x0, y0, table_width, table_height), 10, 10)

        header_path = QPainterPath()
        header_path.addRoundedRect(QRectF(x0, y0, table_width, header_height), 10, 10)
        painter.fillPath(header_path, QColor(FIELD_HEADER))
        painter.fillRect(QRectF(x0, y0 + header_height - 10, table_width, 10), QColor(FIELD_HEADER))

        painter.setPen(QColor(TEXT_COLOR))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(QRectF(x0, y0, index_width, header_height), Qt.AlignmentFlag.AlignCenter, "Index")
        
        for col_index, column in enumerate(columns):
            rect = QRectF(
                x0 + index_width + (col_index * cell_width),
                y0,
                cell_width,
                header_height,
            )

            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(column))

        for row_index, (_, row) in enumerate(self.df.iterrows()):
            y = y0 + header_height + (row_index * cell_height)
            fill = QColor(FIELD_ROW_ODD if row_index % 2 == 0 else FIELD_ROW_EVEN)
            painter.fillRect(QRectF(x0, y, table_width, cell_height), fill)
            painter.setPen(QPen(QColor("#d3e5cd"), 1))
            painter.drawLine(QPointF(x0, y + cell_height), QPointF(x0 + table_width, y + cell_height))

            row_label = self.row_labels[row_index] if row_index < len(self.row_labels) else row_index + 1
            painter.setPen(QColor(TEXT_COLOR))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(QRectF(x0, y, index_width, cell_height), Qt.AlignmentFlag.AlignCenter, str(row_label))

            for col_index, value in enumerate(row):
                cell_x = x0 + index_width + (col_index * cell_width)
                rect = QRectF(cell_x, y, cell_width, cell_height)
                self.cell_positions[(row_index, col_index)] = rect
                painter.setPen(QPen(QColor("#d9e9d4"), 1))
                painter.drawLine(QPointF(rect.x(), rect.y()), QPointF(rect.x(), rect.y() + rect.height()))

                if self.active_cell == (row_index, col_index):
                    painter.setPen(QPen(QColor(ACCENT_COLOR), 2))
                    painter.setBrush(QColor(FIELD_ACTIVE))
                    painter.drawRoundedRect(rect.adjusted(3, 4, -3, -4), 8, 8)

                range_value = self.safe_df_value(self.range_df, row_index, col_index)
                plot_value = self.safe_df_value(self.plot_df, row_index, col_index)

                painter.setPen(QColor(TEXT_COLOR))
                painter.setFont(QFont("Segoe UI", 7))
                
                if plot_value != "":
                    painter.drawText(rect.adjusted(0, 4, 0, 0), Qt.AlignmentFlag.AlignHCenter, f"P {plot_value}")

                painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                painter.drawText(rect.adjusted(0, 5, 0, -3), Qt.AlignmentFlag.AlignCenter, str(value))

                if range_value != "":
                    badge_width = min(cell_width - 8, max(30, len(str(range_value)) * 7 + 22))
                    badge = QRectF(
                        cell_x + ((cell_width - badge_width) / 2),
                        y + cell_height - 18,
                        badge_width,
                        14,
                    )
                    painter.setPen(QPen(QColor("#d7e9d1"), 1))
                    painter.setBrush(QColor("#f5fbf2"))
                    painter.drawRoundedRect(badge, 6, 6)
                    painter.setPen(QColor(MUTED_COLOR))
                    painter.setFont(QFont("Segoe UI", 7))
                    painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, f"R {range_value}")

        painter.setPen(QPen(QColor("#7ea873"), 2))
        painter.drawLine(QPointF(x0 + index_width, y0), QPointF(x0 + index_width, y0 + table_height))

        if self.active_cell is not None:
            rect = self.cell_positions.get(self.active_cell)
            if rect is not None:
                self.draw_actuator(painter, rect)

    def draw_actuator(self, painter, rect):
        center = self.actuator_current_pos or QPointF(rect.left() + 24, rect.center().y())
        bob = 2.0 if self.actuator_phase % 12 < 6 else -1.0
        arm_start = QPointF(center.x() - 18, center.y() - 12 + bob)
        arm_joint = QPointF(center.x() - 4, center.y() - 4 - bob)
        tool_tip = QPointF(center.x() + 14, center.y())

        halo_alpha = 28 + (self.actuator_phase % 12) * 2
        halo_color = QColor(23, 107, 77, halo_alpha)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo_color)
        painter.drawEllipse(center, 19, 12)

        painter.setPen(QPen(QColor("#0f5138"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawLine(arm_start, arm_joint)
        painter.drawLine(arm_joint, tool_tip)

        painter.setPen(QPen(QColor("#f6b73c"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(tool_tip.x(), tool_tip.y()), QPointF(tool_tip.x() + 7, tool_tip.y() - 6))
        painter.drawLine(QPointF(tool_tip.x(), tool_tip.y()), QPointF(tool_tip.x() + 7, tool_tip.y() + 6))

        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.setBrush(QColor(ACCENT_COLOR))
        painter.drawEllipse(arm_joint, 5, 5)
        painter.setBrush(QColor("#f6b73c"))
        painter.drawEllipse(arm_start, 4, 4)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(15, 81, 56, 230))
        badge = QRectF(center.x() - 22, center.y() + 12, 46, 13)
        painter.drawRoundedRect(badge, 6, 6)
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "ROBOT")

    def draw_empty_state(self, painter):
        painter.setPen(QColor(MUTED_COLOR))
        painter.setFont(QFont("Segoe UI", 12))
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "Carregue uma planilha e gere um mapa para visualizar o campo.",
        )

    def safe_df_value(self, df, row_index, column_index):
        if df is None:
            return ""
        try:
            value = df.iloc[row_index, column_index]
        except (IndexError, KeyError):
            return ""
        if pd.isna(value):
            return ""
        return value


class BiChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.stats = {}
        self.setMinimumHeight(500)

    def set_stats(self, stats):
        self.stats = stats
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))

        painter.setPen(QColor(TEXT_COLOR))
        painter.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        painter.drawText(24, 34, "Inteligência operacional")

        total = self.stats.get("total", 0)
        processed = self.stats.get("processed", 0)
        progress = processed / total if total else 0
        range_totals = self.stats.get("range_totals", {})
        by_range = self.stats.get("by_range", {})
        
        if not range_totals:
            painter.setPen(QColor(MUTED_COLOR))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Gere e transmita um mapa para visualizar as análises.",
            )
            return

        gutter = 20
        top = 58
        left_width = max(250, int(self.width() * 0.28))
        right_width = self.width() - left_width - (gutter * 3)
        top_height = max(210, int(self.height() * 0.48))
        bottom_height = max(190, self.height() - top_height - top - (gutter * 2))

        donut_card = QRectF(gutter, top, left_width, top_height)
        column_card = QRectF((gutter * 2) + left_width, top, right_width, top_height)
        line_card = QRectF(gutter, top + top_height + gutter, right_width, bottom_height)
        pie_card = QRectF((gutter * 2) + right_width, top + top_height + gutter, left_width, bottom_height)

        self.draw_chart_card(painter, donut_card, "Conclusão geral", "células transmitidas")
        self.draw_chart_card(painter, column_card, "Distribuição por range", "volume planejado e concluído")
        self.draw_chart_card(painter, line_card, "Ritmo da transmissão", "evolução acumulada")
        self.draw_chart_card(painter, pie_card, "Composição", "pendente vs. concluído")

        self.draw_donut(painter, donut_card.adjusted(22, 62, -22, -24), progress, processed, total)
        self.draw_column_chart(painter, column_card.adjusted(24, 48, -24, -32), range_totals, by_range)
        self.draw_line_chart(painter, line_card.adjusted(26, 50, -26, -34), self.stats.get("history", []), total)
        self.draw_completion_pie(painter, pie_card.adjusted(28, 50, -28, -30), processed, total)

    def draw_chart_card(self, painter, rect, title, subtitle):
        painter.setPen(QPen(QColor("#e2e8f0"), 1))
        painter.setBrush(QColor("#fbfdff"))
        painter.drawRoundedRect(rect, 18, 18)
        painter.setPen(QColor(TEXT_COLOR))
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        painter.drawText(rect.adjusted(18, 14, -18, 0), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, title)
        painter.setPen(QColor(MUTED_COLOR))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(rect.adjusted(18, 32, -18, 0), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, subtitle)

    def draw_donut(self, painter, rect, progress, processed, total):
        size = min(rect.width(), max(80, rect.height() - 38)) - 8
        donut = QRectF(rect.center().x() - size / 2, rect.top() + 4, size, size)
        ring_width = max(14, min(20, int(size * 0.12)))
        painter.setPen(QPen(QColor("#e2e8f0"), ring_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(donut, 90 * 16, -360 * 16)
        painter.setPen(QPen(QColor(ACCENT_COLOR), ring_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(donut, 90 * 16, int(-360 * progress * 16))
        painter.setPen(QColor(TEXT_COLOR))
        painter.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        painter.drawText(donut, Qt.AlignmentFlag.AlignCenter, f"{int(progress * 100)}%")
        painter.setPen(QColor(MUTED_COLOR))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(QRectF(rect.left(), donut.bottom() + 10, rect.width(), 24), Qt.AlignmentFlag.AlignCenter, f"{processed} / {total} células")

    def draw_column_chart(self, painter, rect, range_totals, by_range):
        ranges = sorted(range_totals.keys(), key=lambda value: int(value) if str(value).isdigit() else str(value))
        ranges = ranges[: min(len(ranges), 12)]
        
        if not ranges:
            return
        
        max_total = max(range_totals.get(range_value, 0) for range_value in ranges) or 1
        group_width = rect.width() / len(ranges)
        chart_bottom = rect.bottom() - 22
        chart_top = rect.top() + 8
        chart_height = chart_bottom - chart_top
        painter.setPen(QPen(QColor("#e2e8f0"), 1))
        
        for step in range(4):
            y = chart_bottom - (chart_height * step / 3)
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        
        for index, range_value in enumerate(ranges):
            x = rect.left() + (index * group_width) + (group_width * 0.2)
            planned = range_totals.get(range_value, 0)
            done = by_range.get(range_value, 0)
            planned_h = chart_height * planned / max_total
            done_h = chart_height * done / max_total
            planned_rect = QRectF(x, chart_bottom - planned_h, group_width * 0.22, planned_h)
            done_rect = QRectF(x + group_width * 0.26, chart_bottom - done_h, group_width * 0.22, done_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#cbd5e1"))
            painter.drawRoundedRect(planned_rect, 5, 5)
            painter.setBrush(QColor(CHART_TEAL))
            painter.drawRoundedRect(done_rect, 5, 5)
            painter.setPen(QColor(MUTED_COLOR))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(QRectF(rect.left() + index * group_width, chart_bottom + 4, group_width, 18), Qt.AlignmentFlag.AlignCenter, str(range_value))
        self.draw_legend(painter, QPointF(rect.left(), rect.bottom() - 2), [("Planejado", "#cbd5e1"), ("Concluído", CHART_TEAL)])

    def draw_line_chart(self, painter, rect, history, total):
        if not history:
            history = [0]
        values = history[-40:]
        max_value = max(total, max(values), 1)
        painter.setPen(QPen(QColor("#e2e8f0"), 1))
        
        for step in range(4):
            y = rect.bottom() - (rect.height() * step / 3)
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        
        if len(values) == 1:
            values = [0, values[0]]
        points = []
        
        for index, value in enumerate(values):
            x = rect.left() + (rect.width() * index / (len(values) - 1))
            y = rect.bottom() - (rect.height() * value / max_value)
            points.append(QPointF(x, y))
        area = QPainterPath()
        area.moveTo(points[0].x(), rect.bottom())
        area.lineTo(points[0])
        
        for point in points[1:]:
            area.lineTo(point)
        area.lineTo(points[-1].x(), rect.bottom())
        area.closeSubpath()
        fill = QLinearGradient(0, rect.top(), 0, rect.bottom())
        fill.setColorAt(0, QColor(37, 99, 235, 90))
        fill.setColorAt(1, QColor(37, 99, 235, 8))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawPath(area)
        line = QPainterPath()
        line.moveTo(points[0])
        
        for point in points[1:]:
            line.lineTo(point)
        painter.setPen(QPen(QColor(CHART_BLUE), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(line)

    def draw_completion_pie(self, painter, rect, processed, total):
        pending = max(total - processed, 0)
        values = [processed, pending]
        colors = [QColor(ACCENT_COLOR), QColor("#e2e8f0")]
        labels = ["Concluído", "Pendente"]
        total_value = sum(values) or 1
        size = min(rect.width(), rect.height()) - 42
        pie = QRectF(rect.center().x() - size / 2, rect.top() + 4, size, size)
        start = 90 * 16
        
        for value, color in zip(values, colors):
            span = int(-360 * (value / total_value) * 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawPie(pie, start, span)
            start += span
        
        self.draw_legend(painter, QPointF(rect.left(), pie.bottom() + 18), [(labels[0], ACCENT_COLOR), (labels[1], "#cbd5e1")])

    def draw_legend(self, painter, origin, items):
        x = origin.x()
        for label, color in items:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(QRectF(x, origin.y(), 10, 10), 3, 3)
            painter.setPen(QColor(MUTED_COLOR))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(QRectF(x + 14, origin.y() - 3, 90, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
            x += 92


class BrandedDialog(QDialog):
    def __init__(self, title, message, kind="info", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.setModal(True)
        self.setFixedWidth(440)
        self.setObjectName("Dialog")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        if LOGO_PATH.exists():
            logo = QLabel()
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pixmap = QPixmap(str(LOGO_PATH))
            logo.setPixmap(pixmap.scaledToWidth(220, Qt.TransformationMode.SmoothTransformation))
            layout.addWidget(logo)

        title_label = QLabel(title)
        title_label.setObjectName("DialogTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        message_label = QLabel(message)
        message_label.setObjectName("DialogMessage")
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(message_label)

        ok_button = QPushButton("OK")
        ok_button.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_button.clicked.connect(self.accept)
        ok_button.setObjectName("DialogButton")
        layout.addWidget(ok_button)

        accent = RED_COLOR if kind == "error" else ACCENT_COLOR
        hover = RED_HOVER if kind == "error" else ACCENT_HOVER
        
        self.setStyleSheet(
            f"""
            QDialog#Dialog {{
                background: #ffffff;
            }}
            QLabel#DialogTitle {{
                color: {TEXT_COLOR};
                font-family: "Segoe UI";
                font-size: 19px;
                font-weight: 600;
            }}
            QLabel#DialogMessage {{
                color: {MUTED_COLOR};
                font-family: "Segoe UI";
                font-size: 13px;
                line-height: 18px;
            }}
            QPushButton#DialogButton {{
                background: {accent};
                color: white;
                border: 0;
                border-radius: 9px;
                min-height: 40px;
                font-family: "Segoe UI";
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton#DialogButton:hover {{
                background: {hover};
            }}
            """
        )


class TransmitWorker(QObject):
    step_started = pyqtSignal(int, int)
    step_finished = pyqtSignal(int, int, object)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, steps, start_step, values):
        super().__init__()
        self.steps = steps
        self.start_step = start_step
        self.values = values
        self.paused = False
        self.cancelled = False

    def run(self):
        try:
            for row_index, column_index in self.steps[self.start_step:]:
                
                if self.cancelled:
                    return
                value = self.values[row_index][column_index]
                
                if value == 0:
                    continue

                self.step_started.emit(row_index, column_index)
                
                while self.paused and not self.cancelled:
                    time.sleep(0.1)
                
                if self.cancelled:
                    return

                status = send_serial(value)
                
                while not status and not self.cancelled:
                    time.sleep(0.1)
                    status = send_serial(value)
                self.step_finished.emit(row_index, column_index, value)
                time.sleep(PROCESS_DELAY_SECONDS)
            self.finished.emit()
        
        except Exception as exc:
            logger.error(f"Unexpected error in transmit worker: {exc}")
            self.error.emit(str(exc))


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.paused = False
        self.processed_results = []
        self.selected_file_path = DEFAULT_TEXT
        self.button_icons = {}
        self.active_view = "map"
        self.current_map_df = None
        self.current_map_range_df = None
        self.current_map_plot_df = None
        self.current_map_row_labels = []
        self.processing_stats = self.empty_processing_stats()
        self.worker_thread = None
        self.worker = None
        self.bi_window = None
        self.processed_view_windows = []

        self.setWindowTitle("Votu FieldOps")
        #self.configure_fluent_theme()
        self.set_window_icon()
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(int(screen.width() * 0.8), int(screen.height() * 0.8))
        self.setMinimumSize(1120, 720)
        self.create_widgets()
        self.apply_styles()

    def set_window_icon(self):
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))
        elif LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))

    def create_widgets(self):
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar_frame = QFrame()
        self.sidebar_frame.setObjectName("Sidebar")
        self.sidebar_frame.setFixedWidth(340)
        sidebar_layout = QVBoxLayout(self.sidebar_frame)
        sidebar_layout.setContentsMargins(18, 22, 18, 22)
        sidebar_layout.setSpacing(12)

        self.main_frame = QWidget()
        self.main_frame.setObjectName("Workspace")
        main_layout = QVBoxLayout(self.main_frame)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(16)

        root_layout.addWidget(self.sidebar_frame)
        root_layout.addWidget(self.main_frame, 1)

        self.create_header(sidebar_layout)
        workflow_label = QLabel("Fluxo de trabalho")
        workflow_label.setObjectName("SidebarSection")
        sidebar_layout.addWidget(workflow_label)
        self.upload_button = self.create_button(BUTTON_TEXT, "upload", BLUE_COLOR, BLUE_HOVER, dark=True)
        self.upload_button.clicked.connect(self.upload_file)
        sidebar_layout.addWidget(self.upload_button)

        self.parcels_label = self.create_field_label(NUM_PASSES_TEXT, "parcels")
        sidebar_layout.addWidget(self.parcels_label)
        self.parcels_entry = QLineEdit()
        self.parcels_entry.setPlaceholderText("1 a 16")
        self.parcels_entry.setObjectName("Input")
        sidebar_layout.addWidget(self.parcels_entry)

        actions_label = QLabel("Ações")
        actions_label.setObjectName("SidebarSection")
        sidebar_layout.addWidget(actions_label)
        self.process_button = self.create_button(MATRIX_TEXT, "map", ACCENT_COLOR, ACCENT_HOVER)
        self.process_button.clicked.connect(self.generate_matrix)
        self.process_button.hide()
        sidebar_layout.addWidget(self.process_button)

        self.bi_button = self.create_button("Dashboard", "analytics", "#eef4f8", "#dfeaf2", dark=True)
        self.bi_button.clicked.connect(self.show_bi_view)
        sidebar_layout.addWidget(self.bi_button)

        self.read_button = self.create_button("Iniciar operação", "send", ACCENT_COLOR, ACCENT_HOVER)
        self.read_button.clicked.connect(self.transmit_data)
        self.read_button.hide()
        sidebar_layout.addWidget(self.read_button)

        self.save_maps_button = self.create_button("Salvar mapas", "save", BLUE_COLOR, BLUE_HOVER, dark=True)
        self.save_maps_button.clicked.connect(self.save_processed_maps)
        self.save_maps_button.hide()
        sidebar_layout.addWidget(self.save_maps_button)

        self.export_pdf_button = self.create_button(
            "Exportar relatório",
            "pdf",
            ACCENT_COLOR,
            ACCENT_HOVER,
        )
        self.export_pdf_button.clicked.connect(self.export_processed_reports)
        self.export_pdf_button.hide()
        sidebar_layout.addWidget(self.export_pdf_button)

        self.pause_button = self.create_button("Pausar", "pause", RED_COLOR, RED_HOVER)
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.hide()
        sidebar_layout.addWidget(self.pause_button)

        history_label = QLabel("Histórico")
        history_label.setObjectName("SidebarSection")
        sidebar_layout.addWidget(history_label)
        self.create_processed_locations_frame(sidebar_layout)

        self.page_header = Card("HeroCard")
        header_layout = QHBoxLayout(self.page_header)
        header_layout.setContentsMargins(22, 18, 22, 18)
        header_layout.setSpacing(14)
        header_text = QVBoxLayout()
        header_text.setSpacing(4)
        
        self.file_path_label = QLabel("Votu FieldOps")
        self.file_path_label.setObjectName("HeroTitle")
        self.file_hint_label = QLabel("Central de planejamento, visualização e transmissão do mapa de plantio.")
        self.file_hint_label.setObjectName("HeroSubtitle")
        header_text.addWidget(self.file_path_label)
        header_text.addWidget(self.file_hint_label)
        self.file_status_label = QLabel("Aguardando planilha")
        self.file_status_label.setObjectName("StatusPill")
        header_layout.addLayout(header_text, 1)
        header_layout.addWidget(self.file_status_label, 0, Qt.AlignmentFlag.AlignTop)
        main_layout.addWidget(self.page_header)

        self.create_selection_frame(main_layout)

        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, 1)
        self.create_result_frame()
        self.stack.addWidget(self.result_frame)
        self.stack.setCurrentWidget(self.result_frame)

    def create_header(self, layout):
        brand_card = Card("BrandCard")
        brand_layout = QVBoxLayout(brand_card)
        brand_layout.setContentsMargins(14, 14, 14, 14)
        brand_layout.setSpacing(8)
        
        if LOGO_PATH.exists():
            logo = QLabel()
            logo.setObjectName("Logo")
            pixmap = QPixmap(str(LOGO_PATH))
            logo.setPixmap(pixmap.scaledToWidth(238, Qt.TransformationMode.SmoothTransformation))
            brand_layout.addWidget(logo)
        else:
            fallback = QLabel("Votu FieldOps")
            fallback.setObjectName("BrandTitle")
            brand_layout.addWidget(fallback)

        subtitle = QLabel("Mapa de campo")
        subtitle.setObjectName("Muted")
        brand_layout.addWidget(subtitle)
        layout.addWidget(brand_card)

    def create_selection_frame(self, layout):
        self.selection_frame = Card()
        selection_layout = QGridLayout(self.selection_frame)
        selection_layout.setContentsMargins(18, 16, 18, 18)
        selection_layout.setHorizontalSpacing(16)
        selection_layout.setVerticalSpacing(10)

        self.booknames_label = self.create_field_label(BOOK_NAMES_TEXT, "location")
        self.booknames_dropdown = QComboBox()
        self.booknames_dropdown.setObjectName("Combo")
        self.booknames_dropdown.currentTextChanged.connect(self.on_bookname_selected)

        self.entries_label = self.create_field_label(ENTRY_TEXT, "entry")
        self.entries_dropdown = QComboBox()
        self.entries_dropdown.setObjectName("Combo")
        self.entries_dropdown.currentTextChanged.connect(self.on_entry_selected)
        self.entries_label.setEnabled(False)
        self.entries_dropdown.setEnabled(False)

        self.tiers_label = self.create_field_label(TIER_TEXT, "tier")
        self.tiers_dropdown = QComboBox()
        self.tiers_dropdown.setObjectName("Combo")
        self.tiers_dropdown.currentTextChanged.connect(self.on_tier_selected)
        self.tiers_label.setEnabled(False)
        self.tiers_dropdown.setEnabled(False)

        self.start_from_label = self.create_field_label(START_FROM_TEXT, "start")
        self.start_from_entry = QLineEdit()
        self.start_from_entry.setPlaceholderText("1 a 96")
        self.start_from_entry.setObjectName("Input")

        selection_layout.addWidget(self.booknames_label, 0, 0, 1, 2)
        selection_layout.addWidget(self.entries_label, 0, 2, 1, 2)
        selection_layout.addWidget(self.booknames_dropdown, 1, 0, 1, 2)
        selection_layout.addWidget(self.entries_dropdown, 1, 2, 1, 2)
        selection_layout.addWidget(self.tiers_label, 2, 0, 1, 2)
        selection_layout.addWidget(self.start_from_label, 2, 2, 1, 2)
        selection_layout.addWidget(self.tiers_dropdown, 3, 0, 1, 2)
        selection_layout.addWidget(self.start_from_entry, 3, 2, 1, 2)
        selection_layout.setRowMinimumHeight(2, 12)
        
        for column in range(4):
            selection_layout.setColumnStretch(column, 1)

        layout.addWidget(self.selection_frame)
        self.selection_frame.hide()

    def create_processed_locations_frame(self, layout):
        self.processed_locations_frame = Card()
        processed_layout = QVBoxLayout(self.processed_locations_frame)
        processed_layout.setContentsMargins(14, 14, 14, 14)
        processed_layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Locais processados")
        title.setObjectName("SectionTitle")
        self.processed_count_label = QLabel("0")
        self.processed_count_label.setObjectName("Badge")
        header.addWidget(title, 1)
        header.addWidget(self.processed_count_label)
        processed_layout.addLayout(header)

        self.processed_scroll = QScrollArea()
        self.processed_scroll.setWidgetResizable(True)
        self.processed_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.processed_scroll.setObjectName("TransparentScroll")
        self.processed_cards_widget = QWidget()
        self.processed_cards_layout = QVBoxLayout(self.processed_cards_widget)
        self.processed_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.processed_cards_layout.setSpacing(12)
        self.empty_processed_label = QLabel("Nenhum mapa salvo nesta sessão.\nOs locais processados aparecerão aqui.")
        self.empty_processed_label.setObjectName("MutedCenter")
        self.empty_processed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.processed_cards_layout.addWidget(self.empty_processed_label)
        self.processed_cards_layout.addStretch(1)
        self.processed_scroll.setWidget(self.processed_cards_widget)
        processed_layout.addWidget(self.processed_scroll, 1)

        layout.addWidget(self.processed_locations_frame, 1)

    def create_result_frame(self):
        self.result_frame = Card()
        result_layout = QVBoxLayout(self.result_frame)
        result_layout.setContentsMargins(18, 18, 18, 18)
        result_layout.setSpacing(12)

        result_header = QHBoxLayout()
        result_text = QVBoxLayout()
        result_text.setSpacing(2)
        self.result_title = QLabel("Mapa de campo")
        self.result_title.setObjectName("SectionTitle")
        result_subtitle = QLabel("Mapa de campo com dados de entry, plot e range por célula.")
        result_subtitle.setObjectName("Muted")
        result_text.addWidget(self.result_title)
        result_text.addWidget(result_subtitle)
        result_header.addLayout(result_text, 1)
        result_layout.addLayout(result_header)

        self.notebook = QTabWidget()
        self.notebook.setObjectName("Tabs")
        self.matrix_tab = QWidget()
        matrix_layout = QVBoxLayout(self.matrix_tab)
        matrix_layout.setContentsMargins(0, 18, 0, 0)
        matrix_layout.setSpacing(0)
        self.map_canvas = MapWidget()
        self.map_scroll = QScrollArea()
        self.map_scroll.setObjectName("MapScroll")
        self.map_scroll.setWidgetResizable(True)
        self.map_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.map_scroll.setWidget(self.map_canvas)
        map_surface = QFrame()
        map_surface.setObjectName("MapSurface")
        map_surface_layout = QVBoxLayout(map_surface)
        map_surface_layout.setContentsMargins(1, 1, 1, 1)
        map_surface_layout.setSpacing(0)
        map_surface_layout.addWidget(self.map_scroll)
        matrix_layout.addWidget(map_surface)

        self.details_tree = QTableWidget()
        self.details_tree.setObjectName("DataTable")
        self.details_tree.setAlternatingRowColors(True)
        details_tab = QWidget()
        details_layout = QVBoxLayout(details_tab)
        details_layout.setContentsMargins(0, 18, 0, 0)
        details_layout.setSpacing(0)
        details_layout.addWidget(self.details_tree)

        self.notebook.addTab(self.matrix_tab, "Mapa")
        self.notebook.addTab(details_tab, "Dados do campo")
        result_layout.addWidget(self.notebook, 1)

    def create_bi_panel(self):
        panel = Card()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Dashboard operacional")
        title.setObjectName("HeroTitle")
        subtitle = QLabel("Dashboard com o processamento dos dados em tempo real.")
        subtitle.setObjectName("HeroSubtitle")
        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)
        layout.addLayout(header)

        cards = QHBoxLayout()
        cards.setSpacing(10)
        
        self.bi_cards = {}
        
        for key, label in [
            ("progress", "Células concluídas"),
            ("range", "Range em foco"),
            ("plot", "Plot em foco"),
            ("entry", "Entry em foco"),
        ]:
            card = Card("MetricCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            label_widget = QLabel(label)
            label_widget.setObjectName("MetricLabel")
            value_widget = QLabel("-")
            value_widget.setObjectName("MetricValue")
            card_layout.addWidget(label_widget)
            card_layout.addWidget(value_widget)
            cards.addWidget(card, 1)
            self.bi_cards[key] = value_widget
        layout.addLayout(cards)

        self.bi_canvas = BiChartWidget()
        self.bi_canvas.setObjectName("Chart")
        layout.addWidget(self.bi_canvas, 2)
        
        return panel

    def create_button(self, text, icon_name, bg, hover, dark=False):
        button = QPushButton(text)
        button.setObjectName("ActionButton")
        button.setProperty("bg", bg)
        button.setProperty("hover", hover)
        button.setProperty("dark", dark)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(44)
        icon = self.button_icon(icon_name, "#111111" if dark else "#ffffff")
        
        if not icon.isNull():
            button.setIcon(icon)
            icon_size = QSize(15, 15) if icon_name == "upload" else QSize(17, 17)
            button.setIconSize(icon_size)
       
        return button

    def create_field_label(self, text, icon_name=None):
        icon = self.button_icon(icon_name, ACCENT_COLOR) if icon_name else None
        
        return IconLabel(text, icon)

    def button_icon(self, name, color="#111111"):
        key = (name, color)
        if key in self.button_icons:
            return self.button_icons[key]
        if name in ("upload", "parcels"):
            icon = self.draw_line_icon(name, color)
            self.button_icons[key] = icon
            return icon
        icon = self.library_icon(name, color)
        if icon.isNull():
            icon = self.draw_line_icon(name, color)
        self.button_icons[key] = icon
        
        return icon

    def library_icon(self, name, color):
        if qta is None:
            return QIcon()

        icon_names = {
            "upload": "fa5s.cloud-upload-alt",
            "map": "fa5s.map-marked-alt",
            "analytics": "fa5s.chart-pie",
            "parcels": "fa5s.th-large",
            "location": "fa5s.map-marked-alt",
            "entry": "fa5s.clipboard-list",
            "tier": "fa5s.layer-group",
            "start": "fa5s.flag-checkered",
            "send": "fa5s.paper-plane",
            "save": "fa5s.save",
            "pdf": "fa5s.file-pdf",
            "pause": "fa5s.pause",
            "play": "fa5s.play",
            "view": "fa5s.eye",
            "chevron-down": "fa5s.chevron-down",
        }
        
        icon_name = icon_names.get(name)
        
        if icon_name is None:
            return QIcon()

        try:
            return qta.icon(icon_name, color=color)
        
        except Exception as exc:
            logger.error(f"Error loading qtawesome icon '{icon_name}': {exc}")
            
            return QIcon()

    def draw_line_icon(self, name, color):
        tinted = QPixmap(32, 32)
        tinted.fill(Qt.GlobalColor.transparent)
        painter = QPainter(tinted)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        icon_color = QColor(color)
        soft_color = QColor(color)
        soft_color.setAlpha(42)
        pen = QPen(icon_color, 2.35, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if name == "upload":
            painter.setPen(QPen(icon_color, 2.1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            cloud = QPainterPath()
            cloud.moveTo(9.5, 20.5)
            cloud.cubicTo(6.8, 20.3, 5.2, 18.5, 5.2, 16.2)
            cloud.cubicTo(5.2, 13.8, 7.1, 12.0, 9.4, 12.0)
            cloud.cubicTo(10.4, 8.9, 13.0, 7.2, 16.0, 7.2)
            cloud.cubicTo(19.2, 7.2, 21.6, 9.1, 22.5, 12.0)
            cloud.cubicTo(25.1, 12.4, 26.8, 14.2, 26.8, 16.6)
            cloud.cubicTo(26.8, 19.0, 25.0, 20.5, 22.5, 20.5)
            painter.drawPath(cloud)
            painter.drawLine(16, 12, 16, 24)
            painter.drawLine(QPointF(11.5, 16.5), QPointF(16, 12))
            painter.drawLine(QPointF(20.5, 16.5), QPointF(16, 12))
       
        elif name in ("map", "location"):
            self.draw_map_pin_icon(painter, icon_color, soft_color)
       
        elif name == "analytics":
            painter.drawLine(7, 24, 25, 24)
            painter.drawLine(7, 24, 7, 8)
            painter.setBrush(soft_color)
            painter.drawRoundedRect(10, 17, 3, 7, 1.5, 1.5)
            painter.drawRoundedRect(16, 12, 3, 12, 1.5, 1.5)
            painter.drawRoundedRect(22, 9, 3, 15, 1.5, 1.5)
        
        elif name == "parcels":
            painter.setPen(QPen(icon_color, 1.9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(soft_color)
            
            for x in (6.5, 14.0, 21.5):
                for y in (8.0, 17.0):
                    painter.drawRoundedRect(QRectF(x, y, 5.8, 5.8), 1.8, 1.8)
            
            painter.setPen(QPen(icon_color, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(9.4, 13.8), QPointF(24.4, 13.8))
            painter.drawLine(QPointF(9.4, 16.8), QPointF(24.4, 16.8))
        
        elif name == "entry":
            painter.setBrush(soft_color)
            painter.drawRoundedRect(8, 7, 16, 18, 5, 5)
            painter.drawLine(12, 13, 20, 13)
            painter.drawLine(12, 18, 18, 18)
        
        elif name == "tier":
            painter.drawLine(8, 9, 14, 6)
            painter.drawLine(14, 6, 20, 9)
            painter.drawLine(8, 9, 14, 12)
            painter.drawLine(20, 9, 14, 12)
            painter.drawLine(8, 14, 14, 17)
            painter.drawLine(20, 14, 14, 17)
            painter.drawLine(8, 19, 14, 22)
            painter.drawLine(20, 19, 14, 22)
        
        elif name == "start":
            painter.drawLine(9, 7, 9, 22)
            painter.drawRoundedRect(10, 8, 10, 7, 2, 2)
        
        elif name == "send":
            poly = QPolygonF([QPointF(6, 9), QPointF(26, 16), QPointF(6, 23), QPointF(11, 16)])
            painter.drawPolygon(poly)
            painter.drawLine(11, 16, 26, 16)
        
        elif name == "save":
            painter.setBrush(soft_color)
            painter.drawRoundedRect(8, 6, 16, 20, 4, 4)
            painter.drawLine(11, 6, 21, 6)
            painter.drawRoundedRect(11, 17, 10, 6, 2, 2)

        elif name == "pdf":
            painter.setBrush(soft_color)
            painter.drawRoundedRect(8, 5, 16, 22, 3, 3)
            painter.drawLine(12, 11, 20, 11)
            painter.drawLine(12, 15, 20, 15)
            painter.drawLine(12, 19, 18, 19)
        
        elif name == "pause":
            painter.drawLine(11, 8, 11, 20)
            painter.drawLine(17, 8, 17, 20)
        
        elif name == "play":
            painter.setBrush(QColor(color))
            painter.drawPolygon(QPolygonF([QPointF(10, 7), QPointF(21, 14), QPointF(10, 21)]))
        
        elif name == "view":
            eye = QPainterPath()
            eye.moveTo(5, 16)
            eye.cubicTo(10, 9, 22, 9, 27, 16)
            eye.cubicTo(22, 23, 10, 23, 5, 16)
            painter.drawPath(eye)
            painter.setBrush(icon_color)
            painter.drawEllipse(QPointF(16, 16), 3.2, 3.2)
        
        elif name == "chevron-down":
            painter.drawLine(9, 11, 14, 16)
            painter.drawLine(19, 11, 14, 16)
        
        else:
            painter.drawRoundedRect(7, 7, 14, 14, 4, 4)
        painter.end()
        icon = QIcon(tinted)
        
        return icon

    def draw_map_pin_icon(self, painter, icon_color, soft_color):
        painter.setPen(QPen(icon_color, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(soft_color)
        map_path = QPainterPath()
        map_path.moveTo(5, 9)
        map_path.lineTo(12, 6)
        map_path.lineTo(20, 9)
        map_path.lineTo(27, 6)
        map_path.lineTo(27, 23)
        map_path.lineTo(20, 26)
        map_path.lineTo(12, 23)
        map_path.lineTo(5, 26)
        map_path.closeSubpath()
        painter.drawPath(map_path)
        painter.drawLine(12, 6, 12, 23)
        painter.drawLine(20, 9, 20, 26)

        pin_path = QPainterPath()
        pin_path.moveTo(16, 8)
        pin_path.cubicTo(11.8, 8, 9.4, 11.2, 9.4, 14.7)
        pin_path.cubicTo(9.4, 19.4, 16, 25.3, 16, 25.3)
        pin_path.cubicTo(16, 25.3, 22.6, 19.4, 22.6, 14.7)
        pin_path.cubicTo(22.6, 11.2, 20.2, 8, 16, 8)
        pin_path.closeSubpath()
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(icon_color, 2.1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(pin_path)
        painter.setBrush(icon_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(16, 14.7), 2.25, 2.25)

    def asset_url(self, path):
        return Path(path).resolve().as_posix()

    def apply_styles(self):
        chevron_url = self.asset_url(ICON_ASSETS_PATH / "chevron-down.png")
        button_rules = []
        for bg, hover, text_color in [
            (ACCENT_COLOR, ACCENT_HOVER, "white"),
            (BLUE_COLOR, BLUE_HOVER, "#111111"),
            (RED_COLOR, RED_HOVER, "white"),
            ("#eef4f8", "#dfeaf2", TEXT_COLOR),
        ]:
            button_rules.append(
                f"""
                QPushButton[bg="{bg}"] {{
                    background: {bg};
                    color: {text_color};
                    border: 0;
                    border-radius: 12px;
                    padding: 0 15px;
                    font-family: "Segoe UI";
                    font-size: 12px;
                    font-weight: 600;
                    text-align: left;
                }}
                QPushButton[bg="{bg}"]:hover {{ background: {hover}; }}
                QPushButton[bg="{bg}"]:pressed {{
                    background: {hover};
                    padding-top: 1px;
                }}
                QPushButton[bg="{bg}"]:disabled {{
                    background: #e8eeeb;
                    color: #94a3b8;
                }}
                """
            )

        self.setStyleSheet(
            f"""
            QMainWindow, QWidget#Root {{
                background: #f3f6f8;
            }}
            QWidget {{
                background: transparent;
                color: {TEXT_COLOR};
                font-family: "Segoe UI";
            }}
            #Sidebar {{
                background: rgba(248, 250, 248, 245);
                border-right: 1px solid #e6ece8;
            }}
            QWidget#Workspace {{
                background: #f3f6f8;
            }}
            #Card, Card, QFrame#Card {{
                background: {PANEL_COLOR};
                border: 1px solid rgba(216, 226, 220, 0.72);
                border-radius: 14px;
            }}
            QFrame[objectName="Card"], QFrame#Card {{
                background: {PANEL_COLOR};
                border: 1px solid rgba(216, 226, 220, 0.72);
                border-radius: 14px;
            }}
            QFrame#BrandCard {{
                background: #ffffff;
                border: 1px solid #e4ebe7;
                border-radius: 16px;
            }}
            QFrame#HeroCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ffffff, stop:1 #edf7f1);
                border: 1px solid #dfe9e3;
                border-radius: 18px;
            }}
            QFrame {{
                border: none;
            }}
            QLabel#HeroTitle {{
                font-size: 24px;
                font-weight: 700;
                color: {TEXT_COLOR};
            }}
            QLabel#HeroSubtitle {{
                color: {MUTED_COLOR};
                font-size: 13px;
            }}
            QLabel#StatusPill {{
                background: #e8f3ec;
                color: {ACCENT_COLOR};
                border: 1px solid #cfe4d6;
                border-radius: 14px;
                padding: 6px 12px;
                font-family: "Segoe UI";
                font-size: 12px;
                font-weight: 600;
            }}
            QLabel#BrandTitle {{
                font-size: 20px;
                font-weight: 700;
                color: {TEXT_COLOR};
            }}
            QLabel#SidebarSection {{
                color: #94a3b8;
                font-family: "Segoe UI";
                font-size: 10px;
                font-weight: 800;
                letter-spacing: 1px;
                text-transform: uppercase;
                margin-top: 8px;
            }}
            QLabel#SectionTitle {{
                font-size: 17px;
                font-weight: 700;
                color: {TEXT_COLOR};
            }}
            QLabel#Muted, QLabel#MutedCenter {{
                color: {MUTED_COLOR};
                font-size: 13px;
            }}
            QLabel#Badge {{
                background: #e8edf4;
                color: {MUTED_COLOR};
                border-radius: 10px;
                padding: 2px 10px;
                font-size: 11px;
            }}
            QLabel#FieldLabel {{
                color: {TEXT_COLOR};
                font-size: 12px;
                font-weight: 600;
            }}
            QWidget#IconLabel {{
                background: transparent;
            }}
            QLabel#InlineIcon {{
                background: transparent;
            }}
            QLineEdit#Input, QComboBox#Combo {{
                background: #fbfcfe;
                border: 1px solid #dce5df;
                border-radius: 12px;
                min-height: 44px;
                padding: 0 14px;
                color: {TEXT_COLOR};
                font-family: "Segoe UI";
                font-size: 12px;
            }}
            QLineEdit#Input:focus, QComboBox#Combo:focus {{
                border: 1px solid {ACCENT_COLOR};
                background: #ffffff;
            }}
            QLineEdit#Input:disabled, QComboBox#Combo:disabled {{
                background: #f1f5f3;
                border: 1px solid #e1e8e4;
                color: #94a3b8;
            }}
            QComboBox#Combo:hover {{
                border: 1px solid {ACCENT_COLOR};
            }}
            QComboBox::drop-down {{
                border: 0;
                width: 34px;
                background: {ACCENT_COLOR};
                border-top-right-radius: 12px;
                border-bottom-right-radius: 12px;
            }}
            QComboBox::drop-down:hover {{
                background: {ACCENT_HOVER};
            }}
            QComboBox::drop-down:pressed {{
                background: #0c3f2d;
            }}
            QComboBox::down-arrow {{
                image: url({chevron_url});
                width: 13px;
                height: 13px;
            }}
            QPushButton:disabled {{
                background: #e8eeeb;
                color: #94a3b8;
            }}
            QComboBox QAbstractItemView {{
                background: #ffffff;
                border: 1px solid #cfe0d6;
                border-radius: 12px;
                outline: 0;
                padding: 6px;
                selection-background-color: #dff1e7;
                selection-color: {TEXT_COLOR};
                color: {TEXT_COLOR};
                font-family: "Segoe UI";
                font-size: 12px;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 30px;
                padding: 7px 10px;
                border-radius: 8px;
                margin: 1px 2px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background: #eef8f2;
                color: {ACCENT_COLOR};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background: #dff1e7;
                color: {ACCENT_COLOR};
                font-weight: 700;
            }}
            QComboBox QAbstractItemView QScrollBar:vertical {{
                background: #f0f5f2;
                width: 8px;
                margin: 6px 3px 6px 0;
                border-radius: 4px;
            }}
            QComboBox QAbstractItemView QScrollBar::handle:vertical {{
                background: #b6cbbf;
                border-radius: 4px;
                min-height: 28px;
            }}
            QComboBox QAbstractItemView QScrollBar::handle:vertical:hover {{
                background: #8fb09d;
            }}
            QComboBox QAbstractItemView QScrollBar::add-line:vertical,
            QComboBox QAbstractItemView QScrollBar::sub-line:vertical,
            QComboBox QAbstractItemView QScrollBar::add-page:vertical,
            QComboBox QAbstractItemView QScrollBar::sub-page:vertical {{
                background: transparent;
                border: 0;
            }}
            QTabWidget::pane {{
                border: 0;
                background: transparent;
            }}
            QTabWidget#Tabs::tab-bar {{
                left: 0;
            }}
            QTabBar {{
                background: transparent;
            }}
            QTabBar::tab {{
                background: #f1f4f6;
                color: {TEXT_COLOR};
                border: 0;
                border-radius: 8px;
                min-height: 34px;
                padding: 0 20px;
                margin: 0 6px 0 0;
            }}
            QTabBar::tab:selected {{
                background: #e7f3ec;
                color: {ACCENT_COLOR};
                font-weight: 600;
            }}
            QTabBar::tab:hover:!selected {{
                background: #eaf0ed;
            }}
            QTableWidget#DataTable {{
                background: #fbfcfe;
                alternate-background-color: #f4f7fb;
                border: 1px solid #d8e6dd;
                border-radius: 10px;
                gridline-color: #e4ebf0;
                selection-background-color: #cfe8da;
                selection-color: {TEXT_COLOR};
            }}
            QHeaderView::section {{
                background: #e8edf4;
                color: {TEXT_COLOR};
                border: 0;
                border-right: 1px solid #dce4ec;
                padding: 8px;
                font-weight: 600;
            }}
            QFrame#MetricCard {{
                background: #fbfcfd;
                border: 1px solid #e2e9e5;
                border-radius: 16px;
            }}
            QLabel#MetricLabel {{
                color: {MUTED_COLOR};
                font-size: 12px;
                font-weight: 600;
            }}
            QLabel#MetricValue {{
                color: {TEXT_COLOR};
                font-size: 23px;
                font-weight: 700;
            }}
            QScrollArea#TransparentScroll {{
                background: transparent;
            }}
            QScrollArea#TransparentScroll QWidget {{
                background: transparent;
            }}
            QFrame#MapSurface {{
                background: {FIELD_BG};
                border: 1px solid #d6e7d1;
                border-radius: 10px;
            }}
            QScrollArea#MapScroll {{
                background: transparent;
                border: 0;
                border-radius: 9px;
            }}
            QScrollArea#MapScroll QWidget#qt_scrollarea_viewport {{
                background: {FIELD_BG};
                border-radius: 9px;
            }}
            QScrollArea#MapScroll > QWidget > QWidget {{
                background: {FIELD_BG};
            }}
            QScrollArea#MapScroll QScrollBar:vertical {{
                background: {FIELD_BG};
                width: 10px;
                margin: 5px 3px 5px 2px;
                border-radius: 5px;
            }}
            QScrollArea#MapScroll QScrollBar::handle:vertical {{
                background: #c3d6c9;
                border-radius: 5px;
                min-height: 42px;
            }}
            QScrollArea#MapScroll QScrollBar::handle:vertical:hover {{
                background: #9eb9a8;
            }}
            QScrollArea#MapScroll QScrollBar:horizontal {{
                background: {FIELD_BG};
                height: 10px;
                margin: 2px 5px 3px 5px;
                border-radius: 5px;
            }}
            QScrollArea#MapScroll QScrollBar::handle:horizontal {{
                background: #c3d6c9;
                border-radius: 5px;
                min-width: 42px;
            }}
            QScrollArea#MapScroll QScrollBar::handle:horizontal:hover {{
                background: #9eb9a8;
            }}
            QScrollBar:vertical {{
                background: #eef3f0;
                width: 11px;
                margin: 2px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: #b8c9bf;
                border-radius: 5px;
                min-height: 42px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #8fac9a;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: transparent;
                border: 0;
            }}
            QScrollBar:horizontal {{
                background: #eef3f0;
                height: 11px;
                margin: 2px;
                border-radius: 5px;
            }}
            QScrollBar::handle:horizontal {{
                background: #b8c9bf;
                border-radius: 5px;
                min-width: 42px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: #8fac9a;
            }}
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {{
                background: transparent;
                border: 0;
            }}
            {''.join(button_rules)}
            """
        )
        for frame in [
            self.selection_frame,
            self.result_frame,
            self.processed_locations_frame,
        ]:
            frame.setObjectName("Card")
        self.apply_panel_shadows()

    def apply_panel_shadows(self):
        for widget in [
            self.selection_frame,
            self.result_frame,
            self.processed_locations_frame,
        ]:
            shadow = QGraphicsDropShadowEffect(widget)
            shadow.setBlurRadius(24)
            shadow.setOffset(0, 8)
            shadow.setColor(QColor(30, 52, 42, 28))
            widget.setGraphicsEffect(shadow)

    def info(self, title, message):
        BrandedDialog(title, message, "info", self).exec()

    def error(self, message):
        BrandedDialog("Erro!", message, "error", self).exec()

    def get_file_path(self):
        return self.selected_file_path

    def set_file_path(self, file_path):
        self.selected_file_path = file_path

    def empty_processing_stats(self):
        return {
            "total": 0,
            "processed": 0,
            "current_entry": "-",
            "current_range": "-",
            "current_plot": "-",
            "by_range": {},
            "range_totals": {},
            "history": [],
        }

    def show_map_view(self):
        self.active_view = "map"
        self.page_header.show()
        if self.get_file_path() != DEFAULT_TEXT:
            self.selection_frame.show()
        self.stack.setCurrentWidget(self.result_frame)

    def show_bi_view(self):
        if self.bi_window is None:
            self.bi_window = QMainWindow(self)
            self.bi_window.setWindowTitle("Dashboard operacional - VOTU FieldOps")
            self.bi_window.setWindowIcon(self.windowIcon())
            self.bi_window.resize(1080, 760)
            self.bi_panel = self.create_bi_panel()
            self.bi_window.setCentralWidget(self.bi_panel)
            shadow = QGraphicsDropShadowEffect(self.bi_panel)
            shadow.setBlurRadius(24)
            shadow.setOffset(0, 8)
            shadow.setColor(QColor(30, 52, 42, 28))
            self.bi_panel.setGraphicsEffect(shadow)
            self.bi_window.setStyleSheet(self.styleSheet())
            self.bi_window.destroyed.connect(self.on_bi_window_destroyed)

        self.bi_window.show()
        self.bi_window.raise_()
        self.bi_window.activateWindow()
        self.refresh_bi_dashboard()

    def on_bi_window_destroyed(self):
        self.bi_window = None

    def refresh_bi_dashboard(self):
        if not hasattr(self, "bi_cards") or not hasattr(self, "bi_canvas"):
            return
        stats = self.processing_stats
        total = stats["total"]
        processed = stats["processed"]
        progress = int((processed / total) * 100) if total else 0
        self.bi_cards["progress"].setText(f"{processed}/{total} ({progress}%)")
        self.bi_cards["range"].setText(str(stats["current_range"]))
        self.bi_cards["plot"].setText(str(stats["current_plot"]))
        self.bi_cards["entry"].setText(str(stats["current_entry"]))
        self.bi_canvas.set_stats(stats)

    def upload_file(self):
        try:
            self.clear_treeview()
            self.clear_processed_cards()
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Escolha a planilha",
                "",
                "Planilhas Excel (*.xlsx)",
            )
            if not file_path:
                return None
            if not file_path.endswith(".xlsx"):
                logger.error("Invalid file type. Please select an .xlsx file.")
                self.error("Tipo de arquivo inválido. Por favor, selecione um .xlsx")
                return None

            self.set_file_path(file_path)
            self.populate_booknames_dropdown()
            self.selection_frame.show()
            self.process_button.show()
            self.file_path_label.setText("Mapa de Plantio")
            self.file_status_label.setText(Path(file_path).name)
            self.show_map_view()
            return file_path
        
        except Exception as exc:
            logger.error(f"Error in upload_file: {exc}")
            self.error(f"Erro ao carregar a planilha: {exc}")
            return None

    def populate_booknames_dropdown(self):
        self.booknames_dropdown.blockSignals(True)
        self.booknames_dropdown.clear()
        self.booknames_dropdown.addItems(to_list(self.get_booknames()))
        self.booknames_dropdown.blockSignals(False)
        self.on_bookname_selected(self.booknames_dropdown.currentText())

    def display_entries_dropdown(self):
        selected_bookname = self.get_selected_bookname()
        if not selected_bookname:
            return
        self.entries_dropdown.blockSignals(True)
        self.entries_dropdown.clear()
        self.entries_dropdown.addItems(to_list(self.get_entries(selected_bookname)))
        has_entries = self.entries_dropdown.count() > 0
        if has_entries:
            self.entries_dropdown.setCurrentIndex(0)
        self.entries_dropdown.blockSignals(False)
        self.entries_label.setEnabled(bool(selected_bookname))
        self.entries_dropdown.setEnabled(has_entries)
        if has_entries:
            self.on_entry_selected(self.entries_dropdown.currentText())

    def display_tiers_dropdown(self):
        selected_bookname = self.get_selected_bookname()
        selected_entry = self.get_selected_entry()
        if not selected_bookname or not selected_entry:
            return
        self.tiers_dropdown.blockSignals(True)
        self.tiers_dropdown.clear()
        self.tiers_dropdown.addItems(to_list(self.get_tiers(selected_bookname, selected_entry)))
        has_tiers = self.tiers_dropdown.count() > 0
        if has_tiers:
            self.tiers_dropdown.setCurrentIndex(0)
        self.tiers_dropdown.blockSignals(False)
        self.tiers_label.setEnabled(bool(selected_entry))
        self.tiers_dropdown.setEnabled(has_tiers)
        if has_tiers:
            self.on_tier_selected(self.tiers_dropdown.currentText())

    def on_bookname_selected(self, _selected_bookname=None):
        selected_bookname = self.get_selected_bookname()
        self.entries_dropdown.clear()
        self.tiers_dropdown.clear()
        self.entries_label.setEnabled(bool(selected_bookname))
        self.entries_dropdown.setEnabled(False)
        self.tiers_label.setEnabled(False)
        self.tiers_dropdown.setEnabled(False)
        if selected_bookname:
            self.display_entries_dropdown()

    def on_entry_selected(self, _selected_entry=None):
        selected_entry = self.get_selected_entry()
        self.tiers_dropdown.clear()
        self.tiers_label.setEnabled(bool(selected_entry))
        self.tiers_dropdown.setEnabled(False)
        if selected_entry:
            self.display_tiers_dropdown()

    def on_tier_selected(self, _selected_tier=None):
        return

    def get_booknames(self):
        return booknames_list(read_data_from_excel(self.get_file_path()))

    def get_entries(self, selected_bookname):
        df = read_data_from_excel(self.get_file_path())
        if selected_bookname:
            df = df[df["Book Name"] == selected_bookname]
        return entries_list(df)

    def get_tiers(self, selected_bookname, selected_entry):
        df = read_data_from_excel(self.get_file_path())
        if selected_bookname:
            df = df[df["Book Name"] == selected_bookname]
        return tiers_list(df, selected_entry)

    def get_selected_bookname(self):
        return self.booknames_dropdown.currentText()

    def get_selected_entry(self):
        return self.entries_dropdown.currentText()

    def get_selected_tier(self):
        value = self.tiers_dropdown.currentText()
        return value if value else None

    def get_start_from(self):
        start_from = self.start_from_entry.text().strip()
        return int(start_from) if start_from else None

    def display_dataframe(self, df, table=None, reset_start=True, row_header="#", invert_row_labels=False):
        try:
            if df is None:
                self.error("Nenhum dado encontrado para exibir.")
                return
            if reset_start:
                self.start_from_entry.clear()

            total_rows = len(df.index)
            row_labels = [
                total_rows - row_number + 1 if invert_row_labels else row_number
                for row_number in range(1, total_rows + 1)
            ]

            if table is None or table == "map":
                self.current_map_df = df.copy()
                self.current_map_range_df = df.attrs.get("range_matrix")
                self.current_map_plot_df = df.attrs.get("plot_matrix")
                self.current_map_row_labels = row_labels
                self.map_canvas.set_data(
                    self.current_map_df,
                    self.current_map_range_df,
                    self.current_map_plot_df,
                    self.current_map_row_labels,
                )
                return

            self.populate_table(table, df, row_labels, row_header)
        except Exception as exc:
            logger.error(f"Error in display_dataframe: {exc}")
            self.error(f"Erro ao exibir a planilha: {exc}")

    def populate_table(self, table, df, row_labels, row_header):
        table.clear()
        table.setRowCount(len(df.index))
        table.setColumnCount(len(df.columns) + 1)
        table.setHorizontalHeaderLabels([row_header] + [str(column) for column in df.columns])
        table.verticalHeader().hide()
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

        for row_index, (_, row) in enumerate(df.iterrows()):
            index_item = QTableWidgetItem(str(row_labels[row_index]))
            index_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row_index, 0, index_item)
            for col_index, value in enumerate(row, start=1):
                item = QTableWidgetItem("" if pd.isna(value) else str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row_index, col_index, item)

    def row_labels_for_dataframe(self, df, invert_row_labels=False):
        total_rows = len(df.index)
        return [
            total_rows - row_number + 1 if invert_row_labels else row_number
            for row_number in range(1, total_rows + 1)
        ]

    def create_processed_view_window(self, saved):
        window = QMainWindow(self)
        title_parts = [str(saved["book_name"]), str(saved["entry"])]
        if saved["tier"] is not None:
            title_parts.append(f"Tier {saved['tier']}")
        window.setWindowTitle("Mapa processado - " + " | ".join(title_parts))
        window.setWindowIcon(self.windowIcon())
        window.resize(1080, 740)

        content = Card("Card")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(18, 18, 18, 18)
        content_layout.setSpacing(12)

        header = QVBoxLayout()
        header.setSpacing(3)
        title = QLabel(str(saved["book_name"]))
        title.setObjectName("SectionTitle")
        subtitle_text = str(saved["entry"])
        if saved["tier"] is not None:
            subtitle_text = f"{subtitle_text} | Tier {saved['tier']}"
        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("Muted")
        header.addWidget(title)
        header.addWidget(subtitle)
        content_layout.addLayout(header)

        tabs = QTabWidget()
        tabs.setObjectName("Tabs")

        map_tab = QWidget()
        map_layout = QVBoxLayout(map_tab)
        map_layout.setContentsMargins(0, 18, 0, 0)
        map_layout.setSpacing(0)
        map_canvas = MapWidget()
        map_scroll = QScrollArea()
        map_scroll.setObjectName("MapScroll")
        map_scroll.setWidgetResizable(True)
        map_scroll.setFrameShape(QFrame.Shape.NoFrame)
        map_scroll.setWidget(map_canvas)
        map_surface = QFrame()
        map_surface.setObjectName("MapSurface")
        map_surface_layout = QVBoxLayout(map_surface)
        map_surface_layout.setContentsMargins(1, 1, 1, 1)
        map_surface_layout.setSpacing(0)
        map_surface_layout.addWidget(map_scroll)
        map_layout.addWidget(map_surface)

        result = saved["result"].copy()
        range_matrix = saved.get("range_matrix")
        plot_matrix = saved.get("plot_matrix")
        row_labels = self.row_labels_for_dataframe(result, invert_row_labels=True)
        map_canvas.set_data(result, range_matrix, plot_matrix, row_labels)

        details_table = QTableWidget()
        details_table.setObjectName("DataTable")
        details_table.setAlternatingRowColors(True)
        details_tab = QWidget()
        details_layout = QVBoxLayout(details_tab)
        details_layout.setContentsMargins(0, 18, 0, 0)
        details_layout.setSpacing(0)
        details_layout.addWidget(details_table)
        details_labels = self.row_labels_for_dataframe(saved["details"])
        self.populate_table(details_table, saved["details"], details_labels, "Index")

        tabs.addTab(map_tab, "Mapa")
        tabs.addTab(details_tab, "Dados do campo")
        content_layout.addWidget(tabs, 1)
        window.setCentralWidget(content)
        window.setStyleSheet(self.styleSheet())
        window.destroyed.connect(lambda _obj=None, item=window: self.forget_processed_view_window(item))
        return window

    def field_details_dataframe(self, df, book_name, entry, tier):
        filtered_df = df[(df["Book Name"] == book_name) & (df["Entry Book Name"] == entry)].copy()
        tier_column = get_tier_column(filtered_df)
        plot_column = "Plot #" if "Plot #" in filtered_df.columns else "PLOT#"
        if plot_column not in filtered_df.columns and "B-Plot#" in filtered_df.columns:
            plot_column = "B-Plot#"
        if tier and tier_column in filtered_df.columns:
            filtered_df = filtered_df[filtered_df[tier_column].astype(str) == str(tier)]
        columns = [
            column
            for column in [tier_column, "Range", plot_column, "Entry #"]
            if column and column in filtered_df.columns
        ]
        if not columns:
            return filtered_df
        sort_columns = [column for column in [tier_column, "Range", plot_column] if column in columns]
        return filtered_df[columns].sort_values(by=sort_columns, kind="stable")

    def generate_matrix(self):
        try:
            if self.get_file_path() == DEFAULT_TEXT:
                logger.error("No file selected.")
                self.error("Nenhuma planilha selecionada.")
                return
            parcels_per_row = int(self.parcels_entry.text())
            if parcels_per_row < 1 or parcels_per_row > 16:
                logger.error("Invalid number of parcels.")
                self.error("Número de parcelas inválido. Favor inserir um número entre 1 e 16.")
                return
            book_name = self.get_selected_bookname()
            entry = self.get_selected_entry()
            tier = self.get_selected_tier()
            df = read_data_from_excel(self.get_file_path())
            if not book_name:
                self.error("Selecione um Local antes de gerar o mapa.")
                return
            if not entry:
                self.error("Selecione um Ensaio antes de gerar o mapa.")
                return
            if get_tier_column(df) and not tier:
                self.error("Selecione um Tier antes de gerar o mapa.")
                return
            result = main(df, parcels_per_row, book_name, entry, tier)
            details = self.field_details_dataframe(df, book_name, entry, tier)
            if result is None:
                self.error("Não foi possível gerar uma matriz com 96 pots para essa seleção.")
                return
            self.clear_treeview()
            self.display_dataframe(result, "map", row_header="Index", invert_row_labels=True)
            self.display_dataframe(details, self.details_tree, reset_start=False, row_header="Index")
            self.add_processed_card(book_name, entry, tier, result, details)
            self.read_button.show()
            self.save_maps_button.show()
            self.export_pdf_button.show()
            self.show_map_view()
        except Exception as exc:
            logger.error(f"Error in process: {exc}")
            
            self.error(
                "Não foi possível, gerar o mapa: verifique se todas as informacoes foram " \
                "preenchidas corretamente"
            )

    def add_processed_card(self, book_name, entry, tier, result, details):
        card_index = len(self.processed_results)
        range_matrix = result.attrs.get("range_matrix")
        plot_matrix = result.attrs.get("plot_matrix")
        self.processed_results.append(
            {
                "book_name": book_name,
                "entry": entry,
                "tier": tier,
                "result": result.copy(),
                "range_matrix": range_matrix.copy() if range_matrix is not None else None,
                "plot_matrix": plot_matrix.copy() if plot_matrix is not None else None,
                "details": details.copy(),
            }
        )
        self.clear_processed_empty_state()

        card = ProcessedCard()
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 12, 10, 12)
        layout.setSpacing(12)
        icon_label = QLabel()
        icon_label.setPixmap(self.button_icon("location", ACCENT_COLOR).pixmap(24, 24))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedSize(46, 46)
        icon_label.setStyleSheet("background: #e8f4ee; border-radius: 14px;")

        text_layout = QVBoxLayout()
        text_layout.setSpacing(3)
        title = QLabel(str(book_name))
        title.setStyleSheet(
            f"color: {TEXT_COLOR}; font-family: 'Segoe UI'; font-size: 13px; font-weight: 700;"
        )
        title.setWordWrap(True)
        subtitle_text = str(entry)
        if tier is not None:
            subtitle_text = f"{subtitle_text}"
        subtitle = QLabel(subtitle_text)
        subtitle.setStyleSheet(f"color: {MUTED_COLOR}; font-family: 'Segoe UI'; font-size: 11px;")
        subtitle.setWordWrap(True)
        text_layout.addWidget(title)
        text_layout.addWidget(subtitle)
        if tier is not None:
            tier_label = QLabel(f"Tier {tier}")
            tier_label.setStyleSheet(
                "background: #fef3c7; color: #92400e; border-radius: 8px; padding: 2px 6px; "
                "font-family: 'Segoe UI'; font-size: 10px; font-weight: 700;"
            )
            tier_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tier_label.setFixedWidth(48)
            text_layout.addWidget(tier_label)

        view_button = QPushButton()
        view_button.setObjectName("ProcessedViewButton")
        view_button.setToolTip("Visualizar mapa processado")
        view_button.setCursor(Qt.CursorShape.PointingHandCursor)
        view_button.setIcon(self.button_icon("view", "#ffffff"))
        view_button.setIconSize(QSize(16, 16))
        view_button.clicked.connect(lambda _checked=False, index=card_index: self.inspect_processed_card(index))

        layout.addWidget(icon_label)
        layout.addLayout(text_layout, 1)
        layout.addWidget(view_button, 0, Qt.AlignmentFlag.AlignVCenter)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.mousePressEvent = lambda _event, index=card_index: self.inspect_processed_card(index)
        self.processed_cards_layout.insertWidget(self.processed_cards_layout.count() - 1, card)
        self.update_processed_count()

    def clear_processed_empty_state(self):
        if self.empty_processed_label is not None:
            self.empty_processed_label.deleteLater()
            self.empty_processed_label = None

    def clear_processed_cards(self):
        self.processed_results = []
        while self.processed_cards_layout.count() > 1:
            item = self.processed_cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.empty_processed_label = QLabel("Nenhum mapa salvo nesta sessão.\nOs locais processados aparecerão aqui.")
        self.empty_processed_label.setObjectName("MutedCenter")
        self.empty_processed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.processed_cards_layout.insertWidget(0, self.empty_processed_label)
        self.update_processed_count()
        self.save_maps_button.hide()
        self.export_pdf_button.hide()
        self.read_button.hide()
        self.pause_button.hide()

    def update_processed_count(self):
        self.processed_count_label.setText(str(len(self.processed_results)))

    def inspect_processed_card(self, index):
        saved = self.processed_results[index]
        window = self.create_processed_view_window(saved)
        self.processed_view_windows.append(window)
        window.show()
        window.raise_()
        window.activateWindow()

    def forget_processed_view_window(self, window):
        if window in self.processed_view_windows:
            self.processed_view_windows.remove(window)

    def clear_treeview(self):
        self.details_tree.clear()
        self.details_tree.setRowCount(0)
        self.details_tree.setColumnCount(0)
        self.current_map_df = None
        self.current_map_range_df = None
        self.current_map_plot_df = None
        self.current_map_row_labels = []
        self.map_canvas.clear()

    def safe_export_name(self, *parts):
        text = "__".join(str(part) for part in parts if part not in (None, ""))
        text = text.strip() or "mapa_processado"
        for char in '<>:"/\\|?*':
            text = text.replace(char, "_")
        text = "_".join(text.split())
        return text[:120]

    def dataframe_with_index_column(self, df, invert_index=False):
        export_df = df.copy()
        total_rows = len(export_df.index)
        index_values = list(range(total_rows, 0, -1)) if invert_index else list(range(1, total_rows + 1))
        export_df.insert(0, "Index", index_values)
        return export_df

    def unique_export_path(self, folder, filename):
        path = Path(folder) / f"{filename}.xlsx"
        counter = 2
        while path.exists():
            path = Path(folder) / f"{filename}_{counter}.xlsx"
            counter += 1
        return path

    def processed_map_folder(self, saved):
        folder_name = self.safe_export_name(saved["book_name"]) or "local"
        return MAP_EXPORTS_PATH / folder_name

    def unique_pdf_path(self, folder, filename):
        path = Path(folder) / f"{filename}.pdf"
        counter = 2
        while path.exists():
            path = Path(folder) / f"{filename}_{counter}.pdf"
            counter += 1
        return path

    def export_processed_reports(self):
        if not self.processed_results:
            self.error("Nenhum mapa processado para exportar.")
            return

        default_folder = MAP_EXPORTS_PATH / "relatorios_pdf"
        default_folder.mkdir(parents=True, exist_ok=True)
        selected_folder = QFileDialog.getExistingDirectory(
            self,
            "Selecione a pasta para os relatórios PDF",
            str(default_folder),
        )
        if not selected_folder:
            return

        try:
            output_root = Path(selected_folder)
            exported_files = []
            for saved in self.processed_results:
                local_folder = output_root / self.safe_export_name(saved["book_name"])
                tier_label = f"Tier_{saved['tier']}" if saved.get("tier") is not None else None
                filename = self.safe_export_name("Relatorio", saved["entry"], tier_label)
                output_path = self.unique_pdf_path(local_folder, filename)
                exported_files.append(generate_map_report(saved, output_path, LOGO_PATH))

            locations = sorted({str(path.parent) for path in exported_files})
            self.info(
                "Relatórios exportados",
                f"{len(exported_files)} relatório(s) PDF criado(s) com sucesso em:\n"
                + "\n".join(locations),
            )
        except Exception as exc:
            logger.error(f"Error exporting PDF reports: {exc}")
            self.error(f"Erro ao exportar relatórios PDF: {exc}")

    def save_processed_maps(self):
        try:
            if not self.processed_results:
                self.error("Nenhum mapa processado para salvar.")
                return
            saved_count = 0
            saved_folders = set()
            MAP_EXPORTS_PATH.mkdir(parents=True, exist_ok=True)
            for saved in self.processed_results:
                tier_label = f"Tier_{saved['tier']}" if saved["tier"] is not None else None
                folder = self.processed_map_folder(saved)
                folder.mkdir(parents=True, exist_ok=True)
                filename = self.safe_export_name(saved["entry"], tier_label)
                file_path = self.unique_export_path(folder, filename)
                map_df = self.dataframe_with_index_column(saved["result"], invert_index=True)
                range_matrix = saved.get("range_matrix")
                plot_matrix = saved.get("plot_matrix")
                details_df = self.dataframe_with_index_column(saved["details"])

                with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                    map_df.to_excel(writer, sheet_name="Mapa", index=False)
                    if range_matrix is not None:
                        self.dataframe_with_index_column(range_matrix, invert_index=True).to_excel(
                            writer,
                            sheet_name="Ranges",
                            index=False,
                        )
                    if plot_matrix is not None:
                        self.dataframe_with_index_column(plot_matrix, invert_index=True).to_excel(
                            writer,
                            sheet_name="Plots",
                            index=False,
                        )
                    details_df.to_excel(writer, sheet_name="Dados do campo", index=False)
                saved_count += 1
                saved_folders.add(folder)

            folder_text = "\n".join(str(path) for path in sorted(saved_folders))
            self.info("Sucesso!", f"{saved_count} mapa(s) salvo(s) com sucesso em:\n{folder_text}")
        except Exception as exc:
            logger.error(f"Error saving processed maps: {exc}")
            self.error(f"Erro ao salvar mapas processados: {exc}")

    def prepare_processing_stats(self):
        stats = self.empty_processing_stats()
        if self.current_map_df is not None:
            stats["total"] = int((self.current_map_df != 0).sum().sum())
        if self.current_map_range_df is not None and self.current_map_df is not None:
            for row_index in range(len(self.current_map_df.index)):
                for column_index in range(len(self.current_map_df.columns)):
                    entry_value = self.current_map_df.iloc[row_index, column_index]
                    if entry_value == 0:
                        continue
                    range_value = self.current_map_range_df.iloc[row_index, column_index]
                    key = str(range_value)
                    stats["range_totals"][key] = stats["range_totals"].get(key, 0) + 1
                    stats["by_range"].setdefault(key, 0)
        self.processing_stats = stats
        self.refresh_bi_dashboard()

    def toggle_pause(self):
        self.paused = not self.paused
        if self.worker is not None:
            self.worker.paused = self.paused
        self.pause_button.setText("Continuar" if self.paused else "Pausar")
        self.pause_button.setIcon(self.button_icon("play" if self.paused else "pause", "#ffffff"))

    def transmit_data(self):
        try:
            if self.current_map_df is None:
                self.error("Nenhum mapa gerado para transmitir.")
                return
            start_value = self.get_start_from()
            if (start_value is not None) and (start_value < 1 or start_value > 96):
                self.error("Valor inicial inválido. Favor inserir um número entre 1 e 96.")
                return

            values = self.current_map_df.values.tolist()
            row_indices = list(range(len(values)))
            row_indices.reverse()
            transmit_columns = [
                index
                for index, column in enumerate(self.current_map_df.columns)
                if str(column) != "Range"
            ]
            steps = [(row_index, column_index) for column_index in transmit_columns for row_index in row_indices]
            start_step = 0
            if start_value:
                start_step = None
                for step_index, (row_index, column_index) in enumerate(steps):
                    if int(values[row_index][column_index]) == start_value:
                        start_step = step_index
                        break
                if start_step is None:
                    self.error("Valor inicial não encontrado na matriz.")
                    return

            self.pause_button.show()
            self.prepare_processing_stats()
            self.worker_thread = QThread(self)
            self.worker = TransmitWorker(steps, start_step, values)
            self.worker.moveToThread(self.worker_thread)
            self.worker_thread.started.connect(self.worker.run)
            self.worker.step_started.connect(self.on_transmit_step_started)
            self.worker.step_finished.connect(self.on_transmit_step_finished)
            self.worker.finished.connect(self.on_transmit_finished)
            self.worker.error.connect(self.on_transmit_error)
            self.worker.finished.connect(self.worker_thread.quit)
            self.worker.error.connect(self.worker_thread.quit)
            self.worker_thread.finished.connect(self.worker.deleteLater)
            self.worker_thread.finished.connect(self.worker_thread.deleteLater)
            self.worker_thread.start()
        except Exception as exc:
            logger.error(f"Unexpected error in transmit_data: {exc}")
            self.error(f"Erro ao transmitir dados: {exc}")

    def on_transmit_step_started(self, row_index, column_index):
        self.map_canvas.show_tractor_at_cell(row_index, column_index)
        rect = self.map_canvas.cell_positions.get((row_index, column_index))
        if rect is not None and hasattr(self, "map_scroll"):
            horizontal = self.map_scroll.horizontalScrollBar()
            vertical = self.map_scroll.verticalScrollBar()
            viewport = self.map_scroll.viewport().size()
            horizontal.setValue(max(0, int(rect.center().x() - (viewport.width() / 2))))
            vertical.setValue(max(0, int(rect.center().y() - (viewport.height() / 2))))

    def on_transmit_step_finished(self, row_index, column_index, value):
        self.update_processing_stats(row_index, column_index, value)

    def update_processing_stats(self, row_index, column_index, value):
        try:
            range_value = "-"
            plot_value = "-"
            if self.current_map_range_df is not None:
                range_value = self.current_map_range_df.iloc[row_index, column_index]
            if self.current_map_plot_df is not None:
                plot_value = self.current_map_plot_df.iloc[row_index, column_index]
            key = str(range_value)
            self.processing_stats["processed"] += 1
            self.processing_stats["current_entry"] = value
            self.processing_stats["current_range"] = range_value
            self.processing_stats["current_plot"] = plot_value
            if key in self.processing_stats["by_range"]:
                self.processing_stats["by_range"][key] += 1
            self.processing_stats.setdefault("history", []).append(self.processing_stats["processed"])
            self.refresh_bi_dashboard()
        except Exception as exc:
            logger.error(f"Error updating processing stats: {exc}")

    def on_transmit_finished(self):
        book_name = self.get_selected_bookname()
        entry = self.get_selected_entry()
        self.info("Sucesso!", f"Dados transmitidos com sucesso!\n{book_name} | {entry}")
        self.pause_button.hide()
        self.clear_treeview()
        self.worker = None
        self.worker_thread = None

    def on_transmit_error(self, message):
        self.pause_button.hide()
        self.map_canvas.hide_tractor()
        self.error(f"Erro ao transmitir dados: {message}")
        self.worker = None
        self.worker_thread = None

    def closeEvent(self, event):
        if self.worker is not None:
            self.worker.cancelled = True
        if self.worker_thread is not None and self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait(1500)
        super().closeEvent(event)


def draw_splash_corn(painter):
    def alpha_color(color, alpha):
        value = QColor(color)
        value.setAlpha(alpha)
        return value

    painter.save()
    painter.translate(575, 130)
    painter.rotate(-24)

    leaf_pen = QPen(alpha_color("#0f6b45", 170), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    leaf_fill = QLinearGradient(-110, -35, 105, 55)
    leaf_fill.setColorAt(0, QColor(232, 244, 154, 92))
    leaf_fill.setColorAt(0.45, QColor(92, 165, 65, 118))
    leaf_fill.setColorAt(1, QColor(21, 107, 72, 145))

    for mirror in (-1, 1):
        leaf = QPainterPath()
        leaf.moveTo(-102, 0)
        leaf.cubicTo(-56, -58 * mirror, 36, -58 * mirror, 112, -16 * mirror)
        leaf.cubicTo(55, -8 * mirror, -22, 34 * mirror, -102, 0)
        painter.setPen(leaf_pen)
        painter.setBrush(leaf_fill)
        painter.drawPath(leaf)

        vein = QPainterPath()
        vein.moveTo(-92, 0)
        vein.cubicTo(-45, -25 * mirror, 42, -26 * mirror, 100, -13 * mirror)
        painter.setPen(QPen(alpha_color("#e2f0b2", 118), 1.1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(vein)

    cob_fill = QLinearGradient(-85, -25, 92, 24)
    cob_fill.setColorAt(0, QColor("#fff0a8"))
    cob_fill.setColorAt(0.45, QColor("#f6b73c"))
    cob_fill.setColorAt(1, QColor("#d98d18"))
    cob_path = QPainterPath()
    cob_path.moveTo(-94, 0)
    cob_path.cubicTo(-66, -35, 58, -34, 105, -5)
    cob_path.cubicTo(60, 35, -66, 34, -94, 0)
    painter.setPen(QPen(alpha_color("#b77914", 160), 1.6))
    painter.setBrush(cob_fill)
    painter.drawPath(cob_path)

    painter.save()
    painter.setClipPath(cob_path)
    painter.setPen(QPen(alpha_color("#ba7a13", 125), 0.6))
    for row in range(-3, 4):
        y = row * 8
        x_offset = 4 if row % 2 else 0
        for col in range(-10, 12):
            x = (col * 8) + x_offset
            width = 6.4 + (1.2 if abs(row) < 2 else 0)
            height = 7.6 - (abs(row) * 0.32)
            kernel = QRectF(x - width / 2, y - height / 2, width, height)
            painter.setBrush(QColor(255, 205, 64, 176))
            painter.drawEllipse(kernel)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 244, 151, 92))
            painter.drawEllipse(QRectF(kernel.x() + 1.1, kernel.y() + 1.0, width * 0.34, height * 0.32))
            painter.setPen(QPen(alpha_color("#ba7a13", 105), 0.55))
    painter.restore()

    painter.setPen(QPen(alpha_color("#176b4d", 120), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawArc(QRectF(-100, -34, 210, 68), 190 * 16, 150 * 16)
    painter.drawArc(QRectF(-100, -34, 210, 68), 20 * 16, 140 * 16)

    stem_fill = QLinearGradient(-126, -8, -94, 8)
    stem_fill.setColorAt(0, QColor("#f6d66d"))
    stem_fill.setColorAt(1, QColor("#5e9f45"))
    painter.setPen(QPen(alpha_color("#8f8b31", 130), 1.1))
    painter.setBrush(stem_fill)
    painter.drawRoundedRect(QRectF(-126, -8, 34, 16), 7, 7)

    painter.restore()


def create_splash_pixmap(progress=0.0, status_text="Inicializando módulos"):
    pixmap = QPixmap(720, 420)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    rect = QRectF(0, 0, 720, 420)
    background = QLinearGradient(0, 0, 720, 420)
    background.setColorAt(0, QColor("#ffffff"))
    background.setColorAt(0.55, QColor("#f4f8f6"))
    background.setColorAt(1, QColor("#e8f3ed"))
    painter.setPen(QPen(QColor("#dbe7e0"), 1))
    painter.setBrush(background)
    painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 24, 24)

    draw_splash_corn(painter)

    if LOGO_PATH.exists():
        logo = QPixmap(str(LOGO_PATH)).scaledToWidth(260, Qt.TransformationMode.SmoothTransformation)
        painter.drawPixmap(46, 44, logo)
    else:
        painter.setPen(QColor(TEXT_COLOR))
        painter.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        painter.drawText(48, 78, "VOTU")

    painter.setPen(QColor(TEXT_COLOR))
    painter.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
    painter.drawText(QRectF(48, 145, 410, 42), Qt.AlignmentFlag.AlignLeft, "VOTU FieldOps")

    painter.setPen(QColor(MUTED_COLOR))
    painter.setFont(QFont("Segoe UI", 12))
    painter.drawText(
        QRectF(50, 196, 410, 54),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        "Preparando o ambiente operacional para planejamento,\nvisualização e transmissão do mapa de plantio.",
    )

    card_rect = QRectF(48, 286, 624, 72)
    painter.setPen(QPen(QColor("#dbe7e0"), 1))
    painter.setBrush(QColor(255, 255, 255, 215))
    painter.drawRoundedRect(card_rect, 18, 18)

    painter.setPen(QColor(ACCENT_COLOR))
    painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
    painter.drawText(QRectF(72, 304, 500, 22), Qt.AlignmentFlag.AlignLeft, status_text)

    painter.setPen(QColor(MUTED_COLOR))
    painter.setFont(QFont("Segoe UI", 9))
    painter.drawText(QRectF(72, 329, 500, 20), Qt.AlignmentFlag.AlignLeft, "Excel • Field map • BI • Serial transmission")

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#e2e8f0"))
    painter.drawRoundedRect(QRectF(72, 368, 576, 6), 3, 3)
    painter.setBrush(QColor(ACCENT_COLOR))
    painter.drawRoundedRect(QRectF(72, 368, max(14, 576 * progress), 6), 3, 3)

    painter.setPen(QColor(ACCENT_COLOR))
    painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
    painter.drawText(QRectF(590, 344, 58, 18), Qt.AlignmentFlag.AlignRight, f"{int(progress * 100)}%")

    painter.setPen(QColor("#94a3b8"))
    painter.setFont(QFont("Segoe UI", 8))
    painter.drawText(QRectF(48, 386, 624, 18), Qt.AlignmentFlag.AlignRight, "VOTU Robotics")
    painter.end()
    return pixmap


def show_startup_splash(app):
    splash = QSplashScreen(create_splash_pixmap(0.03, "Inicializando VOTU FieldOps"))
    splash.setWindowFlag(Qt.WindowType.FramelessWindowHint)
    splash.show()
    messages = [
        "Carregando interface operacional...",
        "Preparando módulos de leitura da planilha...",
        "Inicializando visualização do mapa de campo...",
        "Sincronizando BI e telemetria de transmissão...",
        "Preparando simulação do atuador robótico...",
        "Abrindo VOTU FieldOps...",
    ]
    for index, message in enumerate(messages, start=1):
        progress = index / len(messages)
        splash.setPixmap(create_splash_pixmap(progress, message))
        splash.repaint()
        app.processEvents()
        time.sleep(0.55)
    return splash


def configure_application_icon(app):
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VOTU.FieldOps")
        except Exception as exc:
            logger.error(f"Error configuring Windows taskbar app id: {exc}")

    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))
    elif LOGO_PATH.exists():
        app.setWindowIcon(QIcon(str(LOGO_PATH)))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    configure_application_icon(app)
    splash = show_startup_splash(app)
    window = App()
    window.show()
    splash.finish(window)
    sys.exit(app.exec())
