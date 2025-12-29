"""Стили для приложения Director."""

# Цветовая схема - тёмная тема в стиле видеоредактора
COLORS = {
    "bg_dark": "#0d0d0d",
    "bg_primary": "#1a1a1a",
    "bg_secondary": "#252525",
    "bg_tertiary": "#2a2a2a",
    "bg_elevated": "#2d2d2d",
    "bg_hover": "#3a3a3a",
    "accent": "#e85d04",
    "accent_hover": "#f77f00",
    "accent_muted": "#dc2f02",
    "text_primary": "#f5f5f5",
    "text_secondary": "#a0a0a0",
    "text_muted": "#666666",
    "border": "#404040",
    "success": "#38b000",
    "error": "#d62828",
    "warning": "#ffaa00",
}

STYLESHEET = f"""
QMainWindow {{
    background-color: {COLORS["bg_dark"]};
}}

QWidget {{
    background-color: {COLORS["bg_primary"]};
    color: {COLORS["text_primary"]};
    font-family: "JetBrains Mono", "Fira Code", "SF Mono", monospace;
    font-size: 13px;
}}

QLabel {{
    background-color: transparent;
    padding: 0;
}}

QLabel#title {{
    font-size: 28px;
    font-weight: bold;
    color: {COLORS["text_primary"]};
    letter-spacing: 2px;
}}

QLabel#subtitle {{
    font-size: 14px;
    color: {COLORS["text_secondary"]};
}}

QPushButton {{
    background-color: {COLORS["bg_secondary"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    padding: 10px 20px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {COLORS["bg_hover"]};
    border-color: {COLORS["accent"]};
}}

QPushButton:pressed {{
    background-color: {COLORS["bg_elevated"]};
}}

QPushButton:disabled {{
    background-color: {COLORS["bg_dark"]};
    color: {COLORS["text_muted"]};
    border-color: {COLORS["bg_secondary"]};
}}

QPushButton#primary {{
    background-color: {COLORS["accent"]};
    border: none;
    color: white;
    font-weight: bold;
}}

QPushButton#primary:hover {{
    background-color: {COLORS["accent_hover"]};
}}

QPushButton#primary:pressed {{
    background-color: {COLORS["accent_muted"]};
}}

QPushButton#primary:disabled {{
    background-color: {COLORS["bg_secondary"]};
    color: {COLORS["text_muted"]};
}}

QPushButton#danger {{
    background-color: transparent;
    border: 1px solid {COLORS["error"]};
    color: {COLORS["error"]};
}}

QPushButton#danger:hover {{
    background-color: {COLORS["error"]};
    color: white;
}}

QLineEdit {{
    background-color: {COLORS["bg_secondary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    padding: 10px 14px;
    color: {COLORS["text_primary"]};
    selection-background-color: {COLORS["accent"]};
}}

QLineEdit:focus {{
    border-color: {COLORS["accent"]};
}}

QLineEdit:disabled {{
    background-color: {COLORS["bg_dark"]};
    color: {COLORS["text_muted"]};
}}

QListWidget {{
    background-color: {COLORS["bg_secondary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 8px;
    padding: 8px;
    outline: none;
}}

QListWidget::item {{
    background-color: {COLORS["bg_elevated"]};
    border-radius: 6px;
    padding: 16px;
    margin: 4px 0;
}}

QListWidget::item:hover {{
    background-color: {COLORS["bg_hover"]};
}}

QListWidget::item:selected {{
    background-color: {COLORS["accent_muted"]};
    border: 1px solid {COLORS["accent"]};
}}

QScrollBar:vertical {{
    background-color: {COLORS["bg_secondary"]};
    width: 10px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS["border"]};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLORS["accent"]};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QDialog {{
    background-color: {COLORS["bg_primary"]};
}}

QMessageBox {{
    background-color: {COLORS["bg_primary"]};
}}

QFrame#separator {{
    background-color: {COLORS["border"]};
}}

QFrame#card {{
    background-color: {COLORS["bg_secondary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 12px;
}}

QStatusBar {{
    background-color: {COLORS["bg_dark"]};
    color: {COLORS["text_secondary"]};
    border-top: 1px solid {COLORS["border"]};
}}

QToolTip {{
    background-color: {COLORS["bg_elevated"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    padding: 6px;
}}
"""


