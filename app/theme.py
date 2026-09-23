#!/usr/bin/env python3
"""theme.py — readable dark-studio visual theme (THEME ONLY, no behavior).

Palette:
  base background #14161b (very dark blue-gray, not pure black)
  panels/cards    #1d2129
  headers/toolbars #232833 (a touch lighter so layers read as distinct)
  primary text    #f2f4f8 (near-white)
  secondary info  #a8b0bd — no dim-gray body text anywhere
"""
from PySide6.QtGui import QColor

BG = "#14161b"
PANEL = "#1d2129"
HEADER = "#232833"
BORDER = "#333a47"
INPUT_BG = "#1d2129"
BUTTON_BG = "#2a303c"
BUTTON_HOVER = "#343c4b"
TEXT = "#f2f4f8"
TEXT_DIM = "#a8b0bd"
TEXT_DISABLED = "#6b7280"
FOCUS_BLUE = "#4d7cff"
FOCUS_LIGHT = "#6ea8ff"
SELECT_ROW = "#2e3a52"
PLAYHEAD = "#ff5252"

# Piano roll / drum grid paint colors
GRID_BEAT = "#262b36"   # subtle but visible beat lines
GRID_BAR = "#3d4457"    # stronger bar lines
ROW_ALT = "#1a1e26"     # black-key rows
ROW_SEP = "#2b303c"     # drum row separators
WAVEFORM = "#4da3ff"    # default waveform line (stem accent overrides)

# Fixed per-stem accent colors, used consistently in the stem list,
# piano-roll notes, and track headers.
STEM_ACCENTS = {
    "drums": "#ff9f43",   # warm orange
    "bass": "#4d7cff",    # deep blue
    "vocals": "#3fd0a7",  # teal
    "guitar": "#ffb84d",  # amber
    "piano": "#a78bfa",   # violet
    "other": "#9aa3b2",   # gray
}
DEFAULT_ACCENT = "#9aa3b2"


def accent_for(label):
    """QColor accent for an engine stem label (unknown -> gray)."""
    return QColor(STEM_ACCENTS.get((label or "").lower(), DEFAULT_ACCENT))


STYLESHEET = f"""
QWidget {{
    background: {BG};
    color: {TEXT};
}}
QMainWindow {{
    background: {BG};
}}
QToolBar {{
    background: {HEADER};
    border: none;
    border-bottom: 1px solid {BORDER};
    spacing: 6px;
    padding: 4px;
}}
QStatusBar {{
    background: {PANEL};
    color: {TEXT_DIM};
}}
QStatusBar::item {{
    border: none;
}}
QLabel {{
    color: {TEXT};
    background: transparent;
}}
QLabel[section="true"] {{
    color: {TEXT_DIM};
    font-weight: bold;
    font-size: 11px;
    letter-spacing: 2px;
    background: transparent;
    padding: 2px 0;
}}
QFrame[card="true"] {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QGroupBox {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 6px;
    color: {TEXT};
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: {TEXT_DIM};
}}
QPushButton {{
    background: {BUTTON_BG};
    border: 1px solid #3d4453;
    border-radius: 4px;
    padding: 6px 14px;
    color: {TEXT};
}}
QPushButton:hover {{
    background: {BUTTON_HOVER};
    border-color: #556074;
}}
QPushButton:pressed {{
    background: {PANEL};
}}
QPushButton:checked {{
    background: #31405c;
    border: 1px solid {FOCUS_BLUE};
}}
QPushButton:focus {{
    border: 1px solid {FOCUS_LIGHT};
    outline: none;
}}
QPushButton:disabled {{
    background: {PANEL};
    color: {TEXT_DISABLED};
    border-color: #2a2f3a;
}}
QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 6px 10px;
    color: {TEXT};
}}
QToolButton:hover {{
    background: {BUTTON_HOVER};
    border-color: #556074;
}}
QToolButton:disabled {{
    color: {TEXT_DISABLED};
}}
QComboBox {{
    background: {BUTTON_BG};
    border: 1px solid #3d4453;
    border-radius: 4px;
    padding: 5px 8px;
    color: {TEXT};
    min-width: 60px;
}}
QComboBox:hover {{
    border-color: #556074;
}}
QComboBox:focus {{
    border: 1px solid {FOCUS_LIGHT};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: {PANEL};
    color: {TEXT};
    selection-background-color: {SELECT_ROW};
    border: 1px solid #3d4453;
    outline: none;
}}
QSpinBox, QDoubleSpinBox {{
    background: {INPUT_BG};
    border: 1px solid #3d4453;
    border-radius: 4px;
    padding: 5px;
    color: {TEXT};
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {FOCUS_LIGHT};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: {BUTTON_BG};
    border: none;
    width: 20px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {BUTTON_HOVER};
}}
QLineEdit {{
    background: {INPUT_BG};
    border: 1px solid #3d4453;
    border-radius: 4px;
    padding: 5px;
    color: {TEXT};
}}
QLineEdit:focus {{
    border: 1px solid {FOCUS_LIGHT};
}}
QCheckBox {{
    color: {TEXT};
    spacing: 8px;
    background: transparent;
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid #3d4453;
    border-radius: 3px;
    background: {INPUT_BG};
}}
QCheckBox::indicator:hover {{
    border-color: #556074;
}}
QCheckBox::indicator:checked {{
    background: {FOCUS_BLUE};
    border-color: {FOCUS_BLUE};
}}
QListWidget {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    color: {TEXT};
    outline: none;
}}
QListWidget::item {{
    padding: 6px 8px;
    border-radius: 3px;
    color: {TEXT};
}}
QListWidget::item:hover {{
    background: #262c38;
}}
QListWidget::item:selected {{
    background: {SELECT_ROW};
    color: {TEXT};
}}
QSlider::groove:horizontal {{
    background: #262c38;
    height: 6px;
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: {FOCUS_BLUE};
    border-radius: 3px;
}}
QSlider::add-page:horizontal {{
    background: #262c38;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {FOCUS_BLUE};
    width: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{
    background: {FOCUS_LIGHT};
}}
QProgressBar {{
    background: #262c38;
    border: 1px solid {BORDER};
    border-radius: 4px;
    text-align: center;
    color: {TEXT};
    min-width: 120px;
}}
QProgressBar::chunk {{
    background: {FOCUS_BLUE};
    border-radius: 3px;
}}
QScrollBar:horizontal {{
    background: {PANEL};
    height: 14px;
    border: none;
}}
QScrollBar:vertical {{
    background: {PANEL};
    width: 14px;
    border: none;
}}
QScrollBar::handle:horizontal, QScrollBar::handle:vertical {{
    background: #3a4152;
    border-radius: 6px;
    min-width: 30px;
    min-height: 30px;
}}
QScrollBar::handle:horizontal:hover, QScrollBar::handle:vertical:hover {{
    background: #4a5468;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    width: 0;
    height: 0;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}
QSplitter::handle {{
    background: {BORDER};
}}
QSplitter::handle:hover {{
    background: #4a5468;
}}
QDialog {{
    background: {PANEL};
}}
QToolTip {{
    background: {BUTTON_BG};
    color: {TEXT};
    border: 1px solid #3d4453;
    padding: 4px;
}}
"""


def apply_theme(app):
    """Apply the dark-studio theme to the QApplication (headless-safe).

    Idempotent: repeated calls are a no-op (font bump applied once).
    """
    if getattr(app, "_stem2midi_themed", False):
        return
    font = app.font()
    font.setPointSize(font.pointSize() + 1)  # 1pt larger than Qt default
    app.setFont(font)
    app.setStyleSheet(STYLESHEET)
    app._stem2midi_themed = True
