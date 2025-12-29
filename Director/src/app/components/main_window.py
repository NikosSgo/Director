"""Главное окно приложения Director."""

from typing import Optional

from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QStatusBar,
)

from app.components.editor_placeholder import EditorPlaceholder
from app.components.project_hub import ProjectHubWidget
from app.models.project import AppState, Project, ProjectState
from app.store import AppStore
from app.utils.rx_qt import QtDisposableMixin


class MainWindow(QMainWindow, QtDisposableMixin):
    """Главное окно приложения."""

    def __init__(self, store: AppStore):
        super().__init__()
        self._store = store
        self._current_project: Optional[Project] = None
        self.init_disposables()

        self.setWindowTitle("Director — Видеоредактор с ИИ")
        self.setMinimumSize(1200, 800)

        self._setup_ui()
        self._setup_subscriptions()

    def _setup_ui(self) -> None:
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._project_hub = ProjectHubWidget(self._store)
        self._stack.addWidget(self._project_hub)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Подключение к сервисам...")

    def _setup_subscriptions(self) -> None:
        self.subscribe(
            self._store.select(lambda s: s.current_project),
            self._on_current_project_changed,
        )

        self.subscribe(
            self._store.select(lambda s: s.project_state),
            self._on_project_state_changed,
        )

        self.subscribe(
            self._store.select(lambda s: (s.engine_connected, s.file_gateway_connected)),
            self._on_connections_changed,
        )

    def _on_current_project_changed(self, project: Optional[Project]) -> None:
        self._current_project = project

        if project:
            self.setWindowTitle(f"Director — {project.name}")
            self._status_bar.showMessage(f"Открыт проект: {project.name}")
        else:
            self.setWindowTitle("Director — Видеоредактор с ИИ")
            self._status_bar.showMessage("Готов к работе")

    def _on_project_state_changed(self, state: ProjectState) -> None:
        match state:
            case ProjectState.OPEN:
                if self._current_project:
                    editor = EditorPlaceholder(self._current_project)
                    self._stack.addWidget(editor)
                    self._stack.setCurrentWidget(editor)

            case ProjectState.CLOSED:
                self._stack.setCurrentIndex(0)
                while self._stack.count() > 1:
                    widget = self._stack.widget(1)
                    self._stack.removeWidget(widget)
                    widget.deleteLater()

            case ProjectState.LOADING:
                self._status_bar.showMessage("Загрузка проекта...")

            case ProjectState.ERROR:
                self._status_bar.showMessage("Ошибка загрузки проекта")

    def _on_connections_changed(self, connections: tuple[bool, bool]) -> None:
        engine_connected, file_gateway_connected = connections
        
        if engine_connected and file_gateway_connected:
            self._status_bar.showMessage("Готов к работе")
        elif engine_connected:
            self._status_bar.showMessage("FileGateway не подключён")
        elif file_gateway_connected:
            self._status_bar.showMessage("DirectorEngine не подключён")
        else:
            self._status_bar.showMessage("Нет подключения к сервисам")

    def show_project_hub(self) -> None:
        from app.store.actions import Action
        self._store.dispatch(Action.close_project())

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._current_project:
            reply = QMessageBox.question(
                self,
                "Закрытие",
                "Вы уверены, что хотите закрыть приложение?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return

        self._project_hub.cleanup()
        self.dispose_all()
        self._store.dispose()

        event.accept()
