"""Панель ассетов (медиафайлы проекта)."""

from dataclasses import dataclass
from typing import Optional, List, Callable
from pathlib import Path
from enum import Enum, auto
import subprocess
import json
import os

from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QTabWidget,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressDialog,
)

from app.api import GatewayClient
from app.utils.styles import COLORS


class AssetType(Enum):
    """Тип ассета."""
    VIDEO = auto()
    AUDIO = auto()
    IMAGE = auto()
    UNKNOWN = auto()


@dataclass
class Asset:
    """Медиа-ассет проекта."""
    id: str
    name: str
    file_path: str  # путь на сервере
    local_path: str  # локальный путь (для превью)
    asset_type: AssetType
    duration_ms: int = 0  # для видео/аудио
    width: int = 0  # для видео/изображений
    height: int = 0
    size_bytes: int = 0
    
    @property
    def duration_str(self) -> str:
        if self.duration_ms <= 0:
            return ""
        seconds = self.duration_ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    @property
    def size_str(self) -> str:
        if self.size_bytes < 1024:
            return f"{self.size_bytes} B"
        elif self.size_bytes < 1024 * 1024:
            return f"{self.size_bytes / 1024:.1f} KB"
        else:
            return f"{self.size_bytes / (1024 * 1024):.1f} MB"


def get_asset_type(file_path: str) -> AssetType:
    """Определить тип ассета по расширению."""
    ext = Path(file_path).suffix.lower()
    
    video_exts = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.wmv', '.flv', '.m4v'}
    audio_exts = {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a', '.wma'}
    image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.tiff'}
    
    if ext in video_exts:
        return AssetType.VIDEO
    elif ext in audio_exts:
        return AssetType.AUDIO
    elif ext in image_exts:
        return AssetType.IMAGE
    else:
        return AssetType.UNKNOWN


def get_media_info(file_path: str) -> dict:
    """Получить информацию о медиафайле через ffprobe."""
    try:
        result = subprocess.run(
            [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                file_path
            ],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            info = {}
            
            # Длительность
            if 'format' in data and 'duration' in data['format']:
                info['duration_ms'] = int(float(data['format']['duration']) * 1000)
            
            # Размеры видео
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    info['width'] = stream.get('width', 0)
                    info['height'] = stream.get('height', 0)
                    break
            
            return info
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    
    return {}


class ImportWorker(QThread):
    """Фоновый поток для импорта файлов."""
    
    progress = pyqtSignal(int, int, str)  # current, total, filename
    file_imported = pyqtSignal(object)  # Asset
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(
        self,
        gateway: GatewayClient,
        files: List[str],
        destination_path: str,
    ):
        super().__init__()
        self._gateway = gateway
        self._files = files
        self._destination_path = destination_path
        self._asset_counter = 0
    
    def run(self):
        total = len(self._files)
        
        for i, file_path in enumerate(self._files):
            try:
                filename = Path(file_path).name
                self.progress.emit(i + 1, total, filename)
                
                # Получаем информацию о файле
                file_size = os.path.getsize(file_path)
                asset_type = get_asset_type(file_path)
                media_info = get_media_info(file_path)
                
                # Определяем подпапку
                subdir = {
                    AssetType.VIDEO: "video",
                    AssetType.AUDIO: "audio",
                    AssetType.IMAGE: "images",
                }.get(asset_type, "other")
                
                dest_dir = f"{self._destination_path}/{subdir}"
                
                # Загружаем файл на сервер
                response = self._gateway.upload_file(
                    local_path=file_path,
                    destination_path=dest_dir,
                    filename=filename,
                    overwrite=False,
                )
                
                if response.success:
                    self._asset_counter += 1
                    asset = Asset(
                        id=f"asset_{self._asset_counter}_{i}",
                        name=filename,
                        file_path=response.file_path,
                        local_path=file_path,
                        asset_type=asset_type,
                        duration_ms=media_info.get('duration_ms', 0),
                        width=media_info.get('width', 0),
                        height=media_info.get('height', 0),
                        size_bytes=file_size,
                    )
                    self.file_imported.emit(asset)
                else:
                    self.error.emit(f"Ошибка загрузки {filename}: {response.error_message}")
                    
            except Exception as e:
                self.error.emit(f"Ошибка импорта {file_path}: {str(e)}")
        
        self.finished.emit()


class AssetListItem(QWidget):
    """Виджет элемента ассета в списке."""
    
    def __init__(self, asset: Asset, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._asset = asset
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)
        
        # Иконка типа
        icon_label = QLabel()
        icon_text = {
            AssetType.VIDEO: "🎬",
            AssetType.AUDIO: "🎵",
            AssetType.IMAGE: "🖼️",
            AssetType.UNKNOWN: "📄",
        }.get(self._asset.asset_type, "📄")
        icon_label.setText(icon_text)
        icon_label.setStyleSheet("font-size: 20px;")
        icon_label.setFixedWidth(30)
        layout.addWidget(icon_label)
        
        # Информация
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        name_label = QLabel(self._asset.name)
        name_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: 500;")
        info_layout.addWidget(name_label)
        
        details = []
        if self._asset.duration_str:
            details.append(self._asset.duration_str)
        if self._asset.width and self._asset.height:
            details.append(f"{self._asset.width}×{self._asset.height}")
        details.append(self._asset.size_str)
        
        details_label = QLabel(" • ".join(details))
        details_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        info_layout.addWidget(details_label)
        
        layout.addLayout(info_layout, stretch=1)
    
    @property
    def asset(self) -> Asset:
        return self._asset


class AssetsPanel(QWidget):
    """Панель управления ассетами проекта."""
    
    asset_selected = pyqtSignal(object)  # Asset
    asset_double_clicked = pyqtSignal(object)  # Asset - добавить на таймлайн
    assets_changed = pyqtSignal()  # ассеты изменились (для автосохранения)
    
    def __init__(
        self,
        project_path: str = "",
        gateway: Optional[GatewayClient] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._project_path = project_path
        self._gateway = gateway
        self._assets: List[Asset] = []
        self._asset_counter = 0
        self._import_worker: Optional[ImportWorker] = None
        
        self._setup_ui()
    
    def set_gateway(self, gateway: GatewayClient) -> None:
        """Установить клиент Gateway."""
        self._gateway = gateway
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Заголовок
        header = QWidget()
        header.setStyleSheet(f"""
            background-color: {COLORS['bg_secondary']};
            border-bottom: 1px solid {COLORS['border']};
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        
        title = QLabel("Медиа")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        import_btn = QPushButton("+ Импорт")
        import_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: white;
                border: none;
                padding: 4px 12px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['accent_hover']};
            }}
        """)
        import_btn.clicked.connect(self._on_import)
        header_layout.addWidget(import_btn)
        
        layout.addWidget(header)
        
        # Поиск
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(8, 8, 8, 8)
        
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍 Поиск...")
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['bg_tertiary']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 6px 10px;
                color: {COLORS['text_primary']};
            }}
            QLineEdit:focus {{
                border-color: {COLORS['accent']};
            }}
        """)
        self._search_input.textChanged.connect(self._on_search)
        search_layout.addWidget(self._search_input)
        
        layout.addLayout(search_layout)
        
        # Вкладки по типам
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background-color: {COLORS['bg_primary']};
            }}
            QTabBar::tab {{
                background-color: {COLORS['bg_secondary']};
                color: {COLORS['text_secondary']};
                padding: 6px 16px;
                border: none;
            }}
            QTabBar::tab:selected {{
                background-color: {COLORS['bg_primary']};
                color: {COLORS['text_primary']};
            }}
        """)
        
        # Список всех
        self._all_list = self._create_asset_list()
        self._tabs.addTab(self._all_list, "Всё")
        
        # Видео
        self._video_list = self._create_asset_list()
        self._tabs.addTab(self._video_list, "Видео")
        
        # Аудио
        self._audio_list = self._create_asset_list()
        self._tabs.addTab(self._audio_list, "Аудио")
        
        # Изображения
        self._image_list = self._create_asset_list()
        self._tabs.addTab(self._image_list, "Фото")
        
        layout.addWidget(self._tabs, stretch=1)
    
    def _create_asset_list(self) -> QListWidget:
        list_widget = QListWidget()
        list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {COLORS['bg_primary']};
                border: none;
            }}
            QListWidget::item {{
                border-bottom: 1px solid {COLORS['border']};
            }}
            QListWidget::item:selected {{
                background-color: {COLORS['bg_hover']};
            }}
            QListWidget::item:hover {{
                background-color: {COLORS['bg_secondary']};
            }}
        """)
        list_widget.setSpacing(0)
        list_widget.itemClicked.connect(self._on_item_clicked)
        list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        list_widget.customContextMenuRequested.connect(self._on_context_menu)
        list_widget.setDragEnabled(True)
        
        return list_widget
    
    def set_project_path(self, path: str) -> None:
        """Установить путь к проекту."""
        self._project_path = path
    
    def add_asset(self, asset: Asset, emit_changed: bool = True) -> None:
        """Добавить ассет."""
        self._assets.append(asset)
        self._update_lists()
        if emit_changed:
            self.assets_changed.emit()
    
    def _update_lists(self) -> None:
        """Обновить все списки."""
        search_text = self._search_input.text().lower()
        
        # Очищаем
        self._all_list.clear()
        self._video_list.clear()
        self._audio_list.clear()
        self._image_list.clear()
        
        for asset in self._assets:
            # Фильтр поиска
            if search_text and search_text not in asset.name.lower():
                continue
            
            # Всё
            self._add_to_list(self._all_list, asset)
            
            # По типам
            if asset.asset_type == AssetType.VIDEO:
                self._add_to_list(self._video_list, asset)
            elif asset.asset_type == AssetType.AUDIO:
                self._add_to_list(self._audio_list, asset)
            elif asset.asset_type == AssetType.IMAGE:
                self._add_to_list(self._image_list, asset)
    
    def _add_to_list(self, list_widget: QListWidget, asset: Asset) -> None:
        item = QListWidgetItem()
        widget = AssetListItem(asset)
        item.setSizeHint(widget.sizeHint())
        item.setData(Qt.ItemDataRole.UserRole, asset)
        list_widget.addItem(item)
        list_widget.setItemWidget(item, widget)
    
    def _on_import(self) -> None:
        """Импорт файлов."""
        if not self._gateway:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Нет подключения к серверу.\nИмпорт недоступен."
            )
            return
        
        if not self._project_path:
            QMessageBox.warning(
                self,
                "Ошибка", 
                "Проект не выбран."
            )
            return
        
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Импорт медиафайлов",
            "",
            "Медиафайлы (*.mp4 *.avi *.mov *.mkv *.webm *.mp3 *.wav *.ogg *.jpg *.jpeg *.png *.gif);;Все файлы (*.*)"
        )
        
        if not files:
            return
        
        # Путь к ассетам проекта
        assets_path = f"{self._project_path}/assets"
        
        # Создаём диалог прогресса
        self._progress = QProgressDialog(
            "Импорт файлов...",
            "Отмена",
            0,
            len(files),
            self
        )
        self._progress.setWindowTitle("Импорт")
        self._progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress.setMinimumDuration(0)
        self._progress.setValue(0)
        
        # Запускаем воркер
        self._import_worker = ImportWorker(
            gateway=self._gateway,
            files=files,
            destination_path=assets_path,
        )
        self._import_worker.progress.connect(self._on_import_progress)
        self._import_worker.file_imported.connect(self._on_file_imported)
        self._import_worker.error.connect(self._on_import_error)
        self._import_worker.finished.connect(self._on_import_finished)
        self._import_worker.start()
    
    @pyqtSlot(int, int, str)
    def _on_import_progress(self, current: int, total: int, filename: str) -> None:
        self._progress.setValue(current)
        self._progress.setLabelText(f"Импорт: {filename}\n({current}/{total})")
        
        if self._progress.wasCanceled():
            self._import_worker.terminate()
    
    @pyqtSlot(object)
    def _on_file_imported(self, asset: Asset) -> None:
        self.add_asset(asset)
    
    @pyqtSlot(str)
    def _on_import_error(self, error: str) -> None:
        print(f"[Import Error] {error}")
    
    @pyqtSlot()
    def _on_import_finished(self) -> None:
        self._progress.close()
        self._import_worker = None
    
    def _on_search(self, text: str) -> None:
        self._update_lists()
    
    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        asset = item.data(Qt.ItemDataRole.UserRole)
        if asset:
            self.asset_selected.emit(asset)
    
    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        asset = item.data(Qt.ItemDataRole.UserRole)
        if asset:
            self.asset_double_clicked.emit(asset)
    
    def _on_context_menu(self, pos) -> None:
        list_widget = self.sender()
        item = list_widget.itemAt(pos)
        
        if not item:
            return
        
        asset = item.data(Qt.ItemDataRole.UserRole)
        if not asset:
            return
        
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLORS['bg_secondary']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
            }}
            QMenu::item:selected {{
                background-color: {COLORS['bg_hover']};
            }}
        """)
        
        add_action = menu.addAction("Добавить на таймлайн")
        add_action.triggered.connect(lambda: self.asset_double_clicked.emit(asset))
        
        menu.addSeparator()
        
        remove_action = menu.addAction("Удалить из проекта")
        remove_action.triggered.connect(lambda: self._remove_asset(asset))
        
        menu.exec(list_widget.mapToGlobal(pos))
    
    def _remove_asset(self, asset: Asset) -> None:
        """Удалить ассет."""
        reply = QMessageBox.question(
            self,
            "Удаление",
            f"Удалить «{asset.name}» из проекта?\n\nФайл на сервере останется.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._assets = [a for a in self._assets if a.id != asset.id]
            self._update_lists()
            self.assets_changed.emit()
