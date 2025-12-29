"""Удалённый браузер файловой системы сервера."""

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.api import GatewayClient
from app.models.project import StorageInfo
from app.utils.styles import COLORS


class BrowseWorker(QThread):
    """Фоновый поток для загрузки директории."""
    
    finished = pyqtSignal(object)  # dict or Exception
    
    def __init__(self, gateway: GatewayClient, path: str):
        super().__init__()
        self._gateway = gateway
        self._path = path
    
    def run(self):
        try:
            response = self._gateway.browse_directory(self._path)
            if response.success:
                result = {
                    "current_path": response.current_path,
                    "parent_path": response.parent_path,
                    "entries": [
                        {
                            "name": e.name,
                            "path": e.path,
                            "is_directory": e.is_directory,
                            "size": e.size,
                        }
                        for e in response.entries
                    ],
                }
                self.finished.emit(result)
            else:
                self.finished.emit(Exception(response.error_message))
        except Exception as e:
            self.finished.emit(e)


class RemoteFileBrowser(QDialog):
    """
    Диалог для навигации по файловой системе через API Gateway.
    """

    directory_selected = pyqtSignal(str)

    def __init__(
        self,
        gateway: GatewayClient,
        storage_info: Optional[StorageInfo] = None,
        initial_path: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._gateway = gateway
        self._storage_info = storage_info
        self._current_path = initial_path
        self._selected_path: Optional[str] = None
        self._worker: Optional[BrowseWorker] = None

        self.setWindowTitle("Выбор директории на сервере")
        self.setMinimumSize(600, 500)

        self._setup_ui()
        self._load_initial_directory()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Информация о хранилище
        if self._storage_info:
            info_text = f"Хранилище: {self._storage_info.hostname} ({self._storage_info.os})"
            if self._storage_info.free_space > 0:
                info_text += f" • Свободно: {self._storage_info.free_space_gb:.1f} ГБ"
            
            storage_label = QLabel(info_text)
            storage_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
            layout.addWidget(storage_label)

        # Быстрый доступ
        if self._storage_info and self._storage_info.root_paths:
            drives_layout = QHBoxLayout()
            drives_label = QLabel("Быстрый доступ:")
            drives_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
            drives_layout.addWidget(drives_label)

            self._drives_combo = QComboBox()
            self._drives_combo.addItems(self._storage_info.root_paths)
            self._drives_combo.currentTextChanged.connect(self._on_drive_selected)
            drives_layout.addWidget(self._drives_combo)

            drives_layout.addStretch()
            layout.addLayout(drives_layout)

        # Панель навигации
        nav_layout = QHBoxLayout()

        self._up_btn = QPushButton("↑ Вверх")
        self._up_btn.clicked.connect(self._go_up)
        nav_layout.addWidget(self._up_btn)

        self._home_btn = QPushButton("🏠 Домой")
        self._home_btn.clicked.connect(self._go_home)
        nav_layout.addWidget(self._home_btn)

        self._path_input = QLineEdit()
        self._path_input.setPlaceholderText("Путь на сервере")
        self._path_input.returnPressed.connect(self._on_path_entered)
        nav_layout.addWidget(self._path_input, stretch=1)

        self._go_btn = QPushButton("Перейти")
        self._go_btn.clicked.connect(self._on_path_entered)
        nav_layout.addWidget(self._go_btn)

        layout.addLayout(nav_layout)

        # Список
        self._list_widget = QListWidget()
        self._list_widget.setSpacing(2)
        self._list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list_widget)

        # Выбранный путь
        selected_layout = QHBoxLayout()
        selected_label = QLabel("Выбрано:")
        selected_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        selected_layout.addWidget(selected_label)

        self._selected_label = QLabel("—")
        self._selected_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold;")
        selected_layout.addWidget(self._selected_label, stretch=1)

        layout.addLayout(selected_layout)

        # Кнопки
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)

        self._select_btn = QPushButton("Выбрать эту папку")
        self._select_btn.setObjectName("primary")
        self._select_btn.clicked.connect(self._on_select)
        buttons_layout.addWidget(self._select_btn)

        layout.addLayout(buttons_layout)

    def _load_initial_directory(self) -> None:
        if self._current_path:
            self._navigate_to(self._current_path)
        elif self._storage_info and self._storage_info.default_projects_path:
            self._navigate_to(self._storage_info.default_projects_path)
        else:
            self._navigate_to("")

    def _navigate_to(self, path: str) -> None:
        self._list_widget.clear()
        self._path_input.setText(path)

        loading_item = QListWidgetItem("Загрузка...")
        loading_item.setFlags(Qt.ItemFlag.NoItemFlags)
        self._list_widget.addItem(loading_item)

        # Запускаем фоновый поток
        self._worker = BrowseWorker(self._gateway, path)
        self._worker.finished.connect(self._on_browse_finished)
        self._worker.start()

    @pyqtSlot(object)
    def _on_browse_finished(self, result) -> None:
        self._list_widget.clear()

        if isinstance(result, Exception):
            error_item = QListWidgetItem(f"Ошибка: {result}")
            error_item.setForeground(Qt.GlobalColor.red)
            error_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list_widget.addItem(error_item)
            return

        listing = result
        self._current_path = listing["current_path"]
        self._path_input.setText(listing["current_path"])
        self._selected_label.setText(listing["current_path"])
        self._selected_path = listing["current_path"]

        self._up_btn.setEnabled(bool(listing["parent_path"]))

        for entry in listing["entries"]:
            if entry["is_directory"]:
                item = QListWidgetItem(f"📁 {entry['name']}")
                item.setData(Qt.ItemDataRole.UserRole, entry)
                self._list_widget.addItem(item)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        entry = item.data(Qt.ItemDataRole.UserRole)
        if entry and entry.get("is_directory"):
            self._navigate_to(entry["path"])

    def _on_selection_changed(self) -> None:
        items = self._list_widget.selectedItems()
        if items:
            entry = items[0].data(Qt.ItemDataRole.UserRole)
            if entry and entry.get("is_directory"):
                self._selected_label.setText(entry["path"])
                self._selected_path = entry["path"]

    def _on_path_entered(self) -> None:
        path = self._path_input.text().strip()
        if path:
            self._navigate_to(path)

    def _on_drive_selected(self, drive: str) -> None:
        if drive:
            self._navigate_to(drive)

    def _go_up(self) -> None:
        if self._current_path:
            parts = self._current_path.rstrip("/\\").rsplit("/", 1)
            if len(parts) > 1:
                parent = parts[0] or "/"
                self._navigate_to(parent)
            else:
                self._navigate_to("/")

    def _go_home(self) -> None:
        if self._storage_info and self._storage_info.home_directory:
            self._navigate_to(self._storage_info.home_directory)
        else:
            self._navigate_to("")

    def _on_select(self) -> None:
        if self._selected_path:
            self.directory_selected.emit(self._selected_path)
            self.accept()

    def get_selected_path(self) -> Optional[str]:
        return self._selected_path
