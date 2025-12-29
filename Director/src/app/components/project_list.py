"""Компонент списка проектов."""

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.models.project import Project
from app.utils.styles import COLORS


class ProjectListItemWidget(QWidget):
    """Виджет элемента списка проектов."""

    # Фиксированная высота элемента списка
    ITEM_HEIGHT = 80

    def __init__(self, project: Project, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.project = project
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        # Название проекта
        self._name_label = QLabel(self.project.name)
        self._name_label.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {COLORS['text_primary']};"
        )
        layout.addWidget(self._name_label)

        # Путь
        self._path_label = QLabel(self.project.path)
        self._path_label.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        self._path_label.setWordWrap(False)
        layout.addWidget(self._path_label)

        # Дата изменения
        date_str = self.project.updated_datetime.strftime("%d.%m.%Y %H:%M")
        self._date_label = QLabel(f"Изменён: {date_str}")
        self._date_label.setStyleSheet(f"font-size: 11px; color: {COLORS['text_secondary']};")
        layout.addWidget(self._date_label)

        # Устанавливаем фиксированную высоту
        self.setFixedHeight(self.ITEM_HEIGHT)

    def sizeHint(self) -> QSize:
        """Возвращает рекомендуемый размер виджета."""
        return QSize(200, self.ITEM_HEIGHT)


class ProjectListWidget(QWidget):
    """
    Компонент списка проектов.
    
    Сигналы:
        project_selected: Проект выбран
        project_double_clicked: Двойной клик по проекту
        open_clicked: Нажата кнопка "Открыть"
        delete_clicked: Нажата кнопка "Удалить"
    """

    project_selected = pyqtSignal(object)  # Project | None
    project_double_clicked = pyqtSignal(Project)
    open_clicked = pyqtSignal(Project)
    delete_clicked = pyqtSignal(Project)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._projects: list[Project] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Заголовок
        header_layout = QHBoxLayout()
        title = QLabel("Недавние проекты")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self._refresh_btn = QPushButton("↻ Обновить")
        header_layout.addWidget(self._refresh_btn)

        layout.addLayout(header_layout)

        # Список проектов
        self._list_widget = QListWidget()
        self._list_widget.setSpacing(4)
        self._list_widget.setUniformItemSizes(False)
        self._list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list_widget)

        # Кнопки управления
        buttons_layout = QHBoxLayout()

        self._open_btn = QPushButton("Открыть")
        self._open_btn.setObjectName("primary")
        self._open_btn.setEnabled(False)
        self._open_btn.clicked.connect(self._on_open_clicked)
        buttons_layout.addWidget(self._open_btn)

        buttons_layout.addStretch()

        self._delete_btn = QPushButton("Удалить")
        self._delete_btn.setObjectName("danger")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        buttons_layout.addWidget(self._delete_btn)

        layout.addLayout(buttons_layout)

    @property
    def refresh_button(self) -> QPushButton:
        """Кнопка обновления для подключения внешних обработчиков."""
        return self._refresh_btn

    def set_projects(self, projects: tuple[Project, ...]) -> None:
        """Обновить список проектов."""
        self._projects = list(projects)
        self._update_list()

    def set_loading(self, loading: bool) -> None:
        """Установить состояние загрузки."""
        self._refresh_btn.setEnabled(not loading)
        self._refresh_btn.setText("Загрузка..." if loading else "↻ Обновить")

    def get_selected_project(self) -> Optional[Project]:
        """Получить выбранный проект."""
        items = self._list_widget.selectedItems()
        if items:
            return items[0].data(Qt.ItemDataRole.UserRole)
        return None

    def _update_list(self) -> None:
        """Обновить отображение списка."""
        self._list_widget.clear()

        # Сортируем по дате изменения (новые сверху)
        sorted_projects = sorted(
            self._projects, key=lambda p: p.updated_at, reverse=True
        )

        for project in sorted_projects:
            item = QListWidgetItem()
            widget = ProjectListItemWidget(project)
            
            # Явно устанавливаем размер элемента
            item.setSizeHint(QSize(
                self._list_widget.viewport().width() - 20,
                ProjectListItemWidget.ITEM_HEIGHT
            ))
            
            item.setData(Qt.ItemDataRole.UserRole, project)
            self._list_widget.addItem(item)
            self._list_widget.setItemWidget(item, widget)

    def _on_selection_changed(self) -> None:
        """Обработка изменения выбора."""
        project = self.get_selected_project()
        has_selection = project is not None
        self._open_btn.setEnabled(has_selection)
        self._delete_btn.setEnabled(has_selection)
        self.project_selected.emit(project)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Обработка двойного клика."""
        project = item.data(Qt.ItemDataRole.UserRole)
        if project:
            self.project_double_clicked.emit(project)

    def _on_open_clicked(self) -> None:
        """Обработка нажатия кнопки "Открыть"."""
        project = self.get_selected_project()
        if project:
            self.open_clicked.emit(project)

    def _on_delete_clicked(self) -> None:
        """Обработка нажатия кнопки "Удалить"."""
        project = self.get_selected_project()
        if project:
            self.delete_clicked.emit(project)
