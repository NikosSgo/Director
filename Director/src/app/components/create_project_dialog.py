"""Диалог создания нового проекта."""

from typing import Optional

from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.api import FileGatewayClient
from app.components.remote_file_browser import RemoteFileBrowser
from app.models.project import StorageInfo
from app.utils.styles import COLORS


class CreateProjectDialog(QDialog):
    """Диалог создания нового проекта."""

    def __init__(
        self,
        file_gateway_client: FileGatewayClient,
        storage_info: Optional[StorageInfo] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._client = file_gateway_client
        self._storage_info = storage_info

        self.setWindowTitle("Новый проект")
        self.setMinimumWidth(550)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Заголовок
        title = QLabel("Создать новый проект")
        title.setObjectName("title")
        title.setStyleSheet("font-size: 20px;")
        layout.addWidget(title)

        # Информация о хранилище
        if self._storage_info:
            storage_info_label = QLabel(
                f"Проект будет создан на: {self._storage_info.hostname}"
            )
            storage_info_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
            layout.addWidget(storage_info_label)

        layout.addSpacing(8)

        # Название проекта
        name_label = QLabel("Название проекта")
        name_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        layout.addWidget(name_label)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Мой видеопроект")
        layout.addWidget(self._name_input)

        # Расположение
        path_label = QLabel("Расположение на сервере")
        path_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        layout.addWidget(path_label)

        path_row = QHBoxLayout()
        self._path_input = QLineEdit()
        self._path_input.setPlaceholderText("Выберите папку на сервере")
        
        if self._storage_info and self._storage_info.default_projects_path:
            self._path_input.setText(self._storage_info.default_projects_path)
        
        path_row.addWidget(self._path_input)

        browse_btn = QPushButton("Обзор...")
        browse_btn.clicked.connect(self._browse_path)
        path_row.addWidget(browse_btn)

        layout.addLayout(path_row)

        # Подсказка
        hint_label = QLabel(
            "💡 Папка проекта будет создана с названием проекта в выбранной директории"
        )
        hint_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)

        layout.addStretch()

        # Кнопки
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)

        create_btn = QPushButton("Создать проект")
        create_btn.setObjectName("primary")
        create_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(create_btn)

        layout.addLayout(buttons_layout)

    def _browse_path(self) -> None:
        dialog = RemoteFileBrowser(
            client=self._client,
            storage_info=self._storage_info,
            initial_path=self._path_input.text(),
            parent=self,
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_path = dialog.get_selected_path()
            if selected_path:
                self._path_input.setText(selected_path)

    def get_project_data(self) -> tuple[str, str]:
        """Получить данные проекта (название, путь)."""
        return self._name_input.text().strip(), self._path_input.text().strip()
