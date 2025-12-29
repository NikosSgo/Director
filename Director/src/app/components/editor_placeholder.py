"""Заглушка для редактора видео."""

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.models.project import Project
from app.utils.styles import COLORS


class EditorPlaceholder(QWidget):
    """Заглушка для редактора видео (будет реализован позже)."""

    def __init__(self, project: Project, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._project = project
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel(f"Проект: {self._project.name}")
        title.setStyleSheet(
            f"font-size: 24px; font-weight: bold; color: {COLORS['text_primary']};"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        path_label = QLabel(f"Путь: {self._project.path}")
        path_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(path_label)

        info_label = QLabel("Редактор видео будет реализован в следующих версиях")
        info_label.setStyleSheet(f"color: {COLORS['text_muted']}; margin-top: 40px;")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info_label)


