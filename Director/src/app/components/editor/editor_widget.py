"""Главный виджет редактора видео."""

from typing import Optional
import uuid

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QPushButton,
    QToolBar,
    QMenuBar,
    QMenu,
    QMessageBox,
)

from app.components.editor.video_player import VideoPlayer
from app.components.editor.timeline import Timeline, Clip, TrackType
from app.components.editor.assets_panel import AssetsPanel, Asset, AssetType
from app.models.project import Project
from app.utils.styles import COLORS


class EditorWidget(QWidget):
    """Главный виджет редактора видео."""
    
    back_to_hub = pyqtSignal()  # вернуться к списку проектов
    
    def __init__(self, project: Project, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._project = project
        
        self._setup_ui()
        self._setup_connections()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Тулбар
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # Основная область (splitter)
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {COLORS['border']};
                height: 4px;
            }}
            QSplitter::handle:hover {{
                background-color: {COLORS['accent']};
            }}
        """)
        
        # Верхняя часть: превью + ассеты
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {COLORS['border']};
                width: 4px;
            }}
            QSplitter::handle:hover {{
                background-color: {COLORS['accent']};
            }}
        """)
        
        # Панель ассетов (слева)
        self._assets_panel = AssetsPanel(self._project.path)
        self._assets_panel.setMinimumWidth(250)
        self._assets_panel.setMaximumWidth(400)
        top_splitter.addWidget(self._assets_panel)
        
        # Центральная часть: превью + инспектор
        center_widget = QWidget()
        center_layout = QHBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        
        # Превью видео
        preview_container = QWidget()
        preview_container.setStyleSheet(f"background-color: {COLORS['bg_dark']};")
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        
        self._video_player = VideoPlayer()
        preview_layout.addWidget(self._video_player)
        
        center_layout.addWidget(preview_container, stretch=2)
        
        # Инспектор (справа)
        inspector = self._create_inspector()
        inspector.setMinimumWidth(200)
        inspector.setMaximumWidth(300)
        center_layout.addWidget(inspector)
        
        top_splitter.addWidget(center_widget)
        top_splitter.setSizes([280, 700])
        
        main_splitter.addWidget(top_splitter)
        
        # Нижняя часть: таймлайн
        self._timeline = Timeline()
        self._timeline.setMinimumHeight(200)
        main_splitter.addWidget(self._timeline)
        
        main_splitter.setSizes([400, 250])
        
        layout.addWidget(main_splitter, stretch=1)
    
    def _create_toolbar(self) -> QWidget:
        toolbar = QWidget()
        toolbar.setFixedHeight(48)
        toolbar.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_secondary']};
                border-bottom: 1px solid {COLORS['border']};
            }}
            QPushButton {{
                background: transparent;
                border: none;
                color: {COLORS['text_primary']};
                padding: 8px 16px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_hover']};
            }}
            QPushButton#back {{
                color: {COLORS['text_secondary']};
            }}
        """)
        
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(4)
        
        # Кнопка назад
        back_btn = QPushButton("← Проекты")
        back_btn.setObjectName("back")
        back_btn.clicked.connect(self.back_to_hub.emit)
        layout.addWidget(back_btn)
        
        # Разделитель
        sep = QLabel("|")
        sep.setStyleSheet(f"color: {COLORS['border']}; padding: 0 8px;")
        layout.addWidget(sep)
        
        # Название проекта
        project_name = QLabel(self._project.name)
        project_name.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold; font-size: 14px;")
        layout.addWidget(project_name)
        
        layout.addStretch()
        
        # Кнопки редактирования
        cut_btn = QPushButton("✂ Разрезать")
        cut_btn.setToolTip("Разрезать клип (C)")
        layout.addWidget(cut_btn)
        
        delete_btn = QPushButton("🗑 Удалить")
        delete_btn.setToolTip("Удалить выбранное (Del)")
        layout.addWidget(delete_btn)
        
        layout.addStretch()
        
        # Кнопки экспорта
        preview_btn = QPushButton("👁 Превью")
        preview_btn.setToolTip("Рендер превью")
        layout.addWidget(preview_btn)
        
        export_btn = QPushButton("📤 Экспорт")
        export_btn.setToolTip("Экспортировать видео")
        export_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: white;
                border-radius: 4px;
                padding: 8px 20px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['accent_hover']};
            }}
        """)
        export_btn.clicked.connect(self._on_export)
        layout.addWidget(export_btn)
        
        return toolbar
    
    def _create_inspector(self) -> QWidget:
        """Создать панель инспектора."""
        inspector = QWidget()
        inspector.setStyleSheet(f"""
            background-color: {COLORS['bg_secondary']};
            border-left: 1px solid {COLORS['border']};
        """)
        
        layout = QVBoxLayout(inspector)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        # Заголовок
        title = QLabel("Свойства")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold;")
        layout.addWidget(title)
        
        # Плейсхолдер
        self._inspector_content = QLabel("Выберите клип\nдля редактирования")
        self._inspector_content.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._inspector_content.setStyleSheet(f"color: {COLORS['text_muted']};")
        layout.addWidget(self._inspector_content, stretch=1)
        
        return inspector
    
    def _setup_connections(self) -> None:
        """Настроить связи между компонентами."""
        
        # Синхронизация плеера и таймлайна
        self._video_player.position_changed.connect(self._timeline.set_playhead)
        
        # Добавление ассета на таймлайн
        self._assets_panel.asset_double_clicked.connect(self._add_asset_to_timeline)
        
        # Выбор клипа на таймлайне
        self._timeline.clip_selected.connect(self._on_clip_selected)
    
    def _add_asset_to_timeline(self, asset: Asset) -> None:
        """Добавить ассет на таймлайн."""
        # Определяем трек
        track_index = 0 if asset.asset_type in (AssetType.VIDEO, AssetType.IMAGE) else 1
        
        # Создаём клип
        clip = Clip(
            id=str(uuid.uuid4()),
            name=asset.name,
            file_path=asset.file_path,
            track_index=track_index,
            start_time=0,  # TODO: найти свободное место
            duration=asset.duration_ms if asset.duration_ms > 0 else 5000,  # 5 сек для изображений
            color=COLORS['accent'] if asset.asset_type == AssetType.VIDEO else COLORS['success'],
        )
        
        self._timeline.add_clip(track_index, clip)
        
        # Загружаем в плеер если видео
        if asset.asset_type == AssetType.VIDEO:
            self._video_player.load(asset.file_path)
    
    def _on_clip_selected(self, clip) -> None:
        """Обработка выбора клипа."""
        if clip:
            self._inspector_content.setText(
                f"Клип: {clip.name}\n\n"
                f"Начало: {clip.start_time // 1000}s\n"
                f"Длительность: {clip.duration // 1000}s"
            )
        else:
            self._inspector_content.setText("Выберите клип\nдля редактирования")
    
    def _on_export(self) -> None:
        """Экспорт видео."""
        QMessageBox.information(
            self,
            "Экспорт",
            "Функция экспорта будет реализована\nс использованием FFmpeg на сервере."
        )
    
    @property
    def project(self) -> Project:
        return self._project

