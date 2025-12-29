"""Главный экран выбора/создания проекта."""

from typing import Optional

from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.components.create_project_dialog import CreateProjectDialog
from app.components.project_list import ProjectListWidget
from app.models.project import AppState, EngineInfo, Project, StorageInfo
from app.store import Action, AppStore
from app.utils.rx_qt import QtDisposableMixin
from app.utils.styles import COLORS


class ProjectHubWidget(QWidget, QtDisposableMixin):
    """Экран управления проектами (Hub)."""

    def __init__(self, store: AppStore, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._store = store
        self._storage_info: Optional[StorageInfo] = None
        self._engine_info: Optional[EngineInfo] = None
        self.init_disposables()
        self._setup_ui()
        self._setup_subscriptions()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Левая панель
        left_panel = self._create_left_panel()
        layout.addWidget(left_panel)

        # Разделитель
        separator = QFrame()
        separator.setObjectName("separator")
        separator.setFixedWidth(1)
        layout.addWidget(separator)

        # Правая панель
        self._project_list = ProjectListWidget()
        self._project_list.refresh_button.clicked.connect(self._on_refresh_clicked)
        self._project_list.project_double_clicked.connect(self._on_project_open)
        self._project_list.open_clicked.connect(self._on_project_open)
        self._project_list.delete_clicked.connect(self._on_project_delete)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(40, 60, 40, 40)
        right_layout.addWidget(self._project_list)

        layout.addWidget(right_panel, stretch=2)

    def _create_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(350)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(40, 60, 40, 40)
        layout.setSpacing(20)

        # Заголовок
        title = QLabel("DIRECTOR")
        title.setObjectName("title")
        layout.addWidget(title)

        subtitle = QLabel("Интерактивный видеоредактор\nс искусственным интеллектом")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)

        layout.addSpacing(40)

        # Кнопка создания проекта
        new_project_btn = QPushButton("✦  Новый проект")
        new_project_btn.setObjectName("primary")
        new_project_btn.setMinimumHeight(48)
        new_project_btn.clicked.connect(self._on_create_project)
        layout.addWidget(new_project_btn)

        layout.addStretch()

        # Информация о сервисах
        self._services_info_label = QLabel("")
        self._services_info_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        self._services_info_label.setWordWrap(True)
        layout.addWidget(self._services_info_label)

        # Статус Engine
        self._engine_status_label = QLabel("● DirectorEngine: проверка...")
        self._engine_status_label.setStyleSheet(f"color: {COLORS['warning']}; font-size: 12px;")
        layout.addWidget(self._engine_status_label)

        # Статус FileGateway
        self._file_gateway_status_label = QLabel("● FileGateway: проверка...")
        self._file_gateway_status_label.setStyleSheet(f"color: {COLORS['warning']}; font-size: 12px;")
        layout.addWidget(self._file_gateway_status_label)

        return panel

    def _setup_subscriptions(self) -> None:
        # Проекты
        self.subscribe(
            self._store.select(lambda s: s.projects),
            self._on_projects_changed,
        )

        # Загрузка
        self.subscribe(
            self._store.select(lambda s: s.is_loading),
            self._on_loading_changed,
        )

        # Engine connection
        self.subscribe(
            self._store.select(lambda s: s.engine_connected),
            self._on_engine_connection_changed,
        )

        # FileGateway connection
        self.subscribe(
            self._store.select(lambda s: s.file_gateway_connected),
            self._on_file_gateway_connection_changed,
        )

        # Engine info
        self.subscribe(
            self._store.select(lambda s: s.engine_info),
            self._on_engine_info_changed,
        )

        # Storage info
        self.subscribe(
            self._store.select(lambda s: s.storage_info),
            self._on_storage_info_changed,
        )

        # Ошибки
        self.subscribe(
            self._store.select(lambda s: s.error_message),
            self._on_error_changed,
        )

    def _on_projects_changed(self, projects: tuple[Project, ...]) -> None:
        self._project_list.set_projects(projects)

    def _on_loading_changed(self, is_loading: bool) -> None:
        self._project_list.set_loading(is_loading)

    def _on_engine_connection_changed(self, is_connected: bool) -> None:
        if is_connected:
            self._engine_status_label.setText("● DirectorEngine: подключено")
            self._engine_status_label.setStyleSheet(f"color: {COLORS['success']}; font-size: 12px;")
        else:
            self._engine_status_label.setText("● DirectorEngine: отключено")
            self._engine_status_label.setStyleSheet(f"color: {COLORS['error']}; font-size: 12px;")

    def _on_file_gateway_connection_changed(self, is_connected: bool) -> None:
        if is_connected:
            self._file_gateway_status_label.setText("● FileGateway: подключено")
            self._file_gateway_status_label.setStyleSheet(f"color: {COLORS['success']}; font-size: 12px;")
        else:
            self._file_gateway_status_label.setText("● FileGateway: отключено")
            self._file_gateway_status_label.setStyleSheet(f"color: {COLORS['error']}; font-size: 12px;")

    def _on_engine_info_changed(self, info: Optional[EngineInfo]) -> None:
        self._engine_info = info
        self._update_services_info()

    def _on_storage_info_changed(self, info: Optional[StorageInfo]) -> None:
        self._storage_info = info
        self._update_services_info()

    def _update_services_info(self) -> None:
        lines = []
        if self._engine_info:
            lines.append(f"Движок: v{self._engine_info.version}")
        if self._storage_info:
            lines.append(f"Хранилище: {self._storage_info.hostname}")
            if self._storage_info.free_space > 0:
                lines.append(f"Свободно: {self._storage_info.free_space_gb:.1f} ГБ")
        
        self._services_info_label.setText("\n".join(lines))

    def _on_error_changed(self, error: Optional[str]) -> None:
        if error:
            QMessageBox.critical(self, "Ошибка", error)
            self._store.dispatch(Action.clear_error())

    def _on_refresh_clicked(self) -> None:
        self._store.dispatch(Action.load_projects_request())

    def _on_create_project(self) -> None:
        if not self._store.state.file_gateway_connected:
            QMessageBox.warning(
                self, "Ошибка",
                "FileGateway не подключён. Невозможно создать проект."
            )
            return

        dialog = CreateProjectDialog(
            file_gateway_client=self._store.file_gateway,
            storage_info=self._storage_info,
            parent=self,
        )
        
        if dialog.exec() == CreateProjectDialog.DialogCode.Accepted:
            name, path = dialog.get_project_data()
            if not name:
                QMessageBox.warning(self, "Ошибка", "Введите название проекта")
                return
            if not path:
                QMessageBox.warning(self, "Ошибка", "Выберите расположение проекта")
                return

            self._store.dispatch(Action.create_project_request(name, path))

    def _on_project_open(self, project: Project) -> None:
        self._store.dispatch(Action.open_project_request(project.id))

    def _on_project_delete(self, project: Project) -> None:
        reply = QMessageBox.question(
            self,
            "Удаление проекта",
            f"Вы уверены, что хотите удалить проект «{project.name}»?\n\n"
            "Файлы проекта на диске НЕ будут удалены.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._store.dispatch(Action.delete_project_request(project.id))

    def cleanup(self) -> None:
        self.dispose_all()
