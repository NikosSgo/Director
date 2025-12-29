"""Компонент таймлайна для редактирования видео."""

from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum, auto

from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QMouseEvent, QWheelEvent
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QLabel,
    QPushButton,
    QSizePolicy,
)

from app.utils.styles import COLORS


class TrackType(Enum):
    """Тип трека."""
    VIDEO = auto()
    AUDIO = auto()
    TEXT = auto()


@dataclass
class Clip:
    """Клип на таймлайне."""
    id: str
    name: str
    file_path: str
    track_index: int
    start_time: int  # мс
    duration: int  # мс
    in_point: int = 0  # мс (начало в исходном файле)
    out_point: int = 0  # мс (конец в исходном файле)
    color: str = COLORS['accent']
    
    @property
    def end_time(self) -> int:
        return self.start_time + self.duration


@dataclass 
class Track:
    """Трек на таймлайне."""
    id: str
    name: str
    track_type: TrackType
    clips: List[Clip] = field(default_factory=list)
    height: int = 60
    muted: bool = False
    locked: bool = False


class TimelineRuler(QWidget):
    """Линейка времени."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.setMinimumWidth(200)
        
        self._zoom = 1.0  # пикселей на секунду
        self._offset = 0  # смещение в пикселях
        self._duration = 60000  # общая длительность в мс
        
    def set_zoom(self, zoom: float) -> None:
        self._zoom = max(0.1, min(zoom, 10.0))
        self.update()
    
    def set_offset(self, offset: int) -> None:
        self._offset = offset
        self.update()
    
    def set_duration(self, duration_ms: int) -> None:
        self._duration = duration_ms
        self.update()
    
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Фон
        painter.fillRect(self.rect(), QColor(COLORS['bg_secondary']))
        
        # Рисуем метки времени
        pixels_per_second = 100 * self._zoom
        
        # Определяем шаг меток
        if pixels_per_second > 200:
            step_seconds = 1
        elif pixels_per_second > 50:
            step_seconds = 5
        elif pixels_per_second > 20:
            step_seconds = 10
        else:
            step_seconds = 30
        
        painter.setPen(QPen(QColor(COLORS['text_muted']), 1))
        painter.setFont(QFont("monospace", 9))
        
        start_second = int(self._offset / pixels_per_second)
        end_second = int((self._offset + self.width()) / pixels_per_second) + 1
        
        for second in range(start_second, end_second + 1):
            x = int(second * pixels_per_second - self._offset)
            
            if second % step_seconds == 0:
                # Большая метка
                painter.drawLine(x, 20, x, 30)
                
                minutes = second // 60
                secs = second % 60
                time_str = f"{minutes:02d}:{secs:02d}"
                painter.drawText(x + 4, 16, time_str)
            else:
                # Малая метка
                painter.drawLine(x, 25, x, 30)
        
        # Нижняя линия
        painter.setPen(QPen(QColor(COLORS['border']), 1))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)


class TimelineTrackWidget(QWidget):
    """Виджет одного трека."""
    
    clip_selected = pyqtSignal(Clip)
    clip_moved = pyqtSignal(Clip, int)  # клип, новая позиция
    
    def __init__(self, track: Track, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._track = track
        self._zoom = 1.0
        self._offset = 0
        self._selected_clip: Optional[Clip] = None
        self._dragging = False
        self._drag_start_x = 0
        self._drag_clip_start = 0
        
        self.setFixedHeight(track.height)
        self.setMinimumWidth(200)
        self.setMouseTracking(True)
    
    def set_zoom(self, zoom: float) -> None:
        self._zoom = zoom
        self.update()
    
    def set_offset(self, offset: int) -> None:
        self._offset = offset
        self.update()
    
    def _time_to_x(self, time_ms: int) -> int:
        """Конвертировать время в координату X."""
        pixels_per_ms = (100 * self._zoom) / 1000
        return int(time_ms * pixels_per_ms - self._offset)
    
    def _x_to_time(self, x: int) -> int:
        """Конвертировать координату X во время."""
        pixels_per_ms = (100 * self._zoom) / 1000
        return int((x + self._offset) / pixels_per_ms)
    
    def _clip_at(self, x: int) -> Optional[Clip]:
        """Найти клип по координате X."""
        for clip in self._track.clips:
            clip_x = self._time_to_x(clip.start_time)
            clip_width = self._time_to_x(clip.end_time) - clip_x
            if clip_x <= x <= clip_x + clip_width:
                return clip
        return None
    
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Фон
        bg_color = COLORS['bg_tertiary'] if self._track.track_type == TrackType.VIDEO else COLORS['bg_secondary']
        painter.fillRect(self.rect(), QColor(bg_color))
        
        # Рисуем клипы
        for clip in self._track.clips:
            self._draw_clip(painter, clip)
        
        # Нижняя граница
        painter.setPen(QPen(QColor(COLORS['border']), 1))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
    
    def _draw_clip(self, painter: QPainter, clip: Clip) -> None:
        x = self._time_to_x(clip.start_time)
        width = self._time_to_x(clip.end_time) - x
        height = self.height() - 8
        y = 4
        
        if width < 2:
            return
        
        # Основной цвет
        color = QColor(clip.color)
        if clip == self._selected_clip:
            color = color.lighter(120)
        
        # Фон клипа
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(color.darker(120), 1))
        painter.drawRoundedRect(QRectF(x, y, width, height), 4, 4)
        
        # Название
        if width > 50:
            painter.setPen(QPen(QColor("#ffffff"), 1))
            painter.setFont(QFont("sans-serif", 9))
            text_rect = QRectF(x + 6, y, width - 12, height)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, clip.name)
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            clip = self._clip_at(int(event.position().x()))
            if clip:
                self._selected_clip = clip
                self._dragging = True
                self._drag_start_x = int(event.position().x())
                self._drag_clip_start = clip.start_time
                self.clip_selected.emit(clip)
                self.update()
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging and self._selected_clip:
            dx = int(event.position().x()) - self._drag_start_x
            new_time = max(0, self._drag_clip_start + self._x_to_time(dx) - self._x_to_time(0))
            self._selected_clip = Clip(
                id=self._selected_clip.id,
                name=self._selected_clip.name,
                file_path=self._selected_clip.file_path,
                track_index=self._selected_clip.track_index,
                start_time=new_time,
                duration=self._selected_clip.duration,
                color=self._selected_clip.color,
            )
            self.update()
    
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._dragging and self._selected_clip:
            self.clip_moved.emit(self._selected_clip, self._selected_clip.start_time)
        self._dragging = False


class Timeline(QWidget):
    """Главный виджет таймлайна."""
    
    position_changed = pyqtSignal(int)  # мс
    clip_selected = pyqtSignal(object)  # Clip or None
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self._tracks: List[Track] = []
        self._track_widgets: List[TimelineTrackWidget] = []
        self._zoom = 1.0
        self._offset = 0
        self._playhead_position = 0  # мс
        self._duration = 60000  # мс
        
        self._setup_ui()
        self._create_default_tracks()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Тулбар
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # Основная область
        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        
        # Панель треков (слева)
        self._track_labels = QWidget()
        self._track_labels.setFixedWidth(150)
        self._track_labels.setStyleSheet(f"background-color: {COLORS['bg_secondary']};")
        self._track_labels_layout = QVBoxLayout(self._track_labels)
        self._track_labels_layout.setContentsMargins(0, 30, 0, 0)  # отступ под ruler
        self._track_labels_layout.setSpacing(0)
        content.addWidget(self._track_labels)
        
        # Область с таймлайном
        timeline_area = QWidget()
        timeline_layout = QVBoxLayout(timeline_area)
        timeline_layout.setContentsMargins(0, 0, 0, 0)
        timeline_layout.setSpacing(0)
        
        # Линейка
        self._ruler = TimelineRuler()
        timeline_layout.addWidget(self._ruler)
        
        # Область треков
        self._tracks_container = QWidget()
        self._tracks_layout = QVBoxLayout(self._tracks_container)
        self._tracks_layout.setContentsMargins(0, 0, 0, 0)
        self._tracks_layout.setSpacing(0)
        
        scroll = QScrollArea()
        scroll.setWidget(self._tracks_container)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(f"background-color: {COLORS['bg_primary']}; border: none;")
        timeline_layout.addWidget(scroll)
        
        content.addWidget(timeline_area, stretch=1)
        
        layout.addLayout(content)
    
    def _create_toolbar(self) -> QWidget:
        toolbar = QWidget()
        toolbar.setFixedHeight(36)
        toolbar.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_secondary']};
                border-bottom: 1px solid {COLORS['border']};
            }}
            QPushButton {{
                background: transparent;
                border: none;
                color: {COLORS['text_primary']};
                padding: 4px 8px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_hover']};
            }}
        """)
        
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(4)
        
        # Кнопки масштаба
        zoom_out = QPushButton("−")
        zoom_out.setToolTip("Уменьшить")
        zoom_out.clicked.connect(lambda: self.set_zoom(self._zoom * 0.8))
        layout.addWidget(zoom_out)
        
        self._zoom_label = QLabel("100%")
        self._zoom_label.setStyleSheet(f"color: {COLORS['text_secondary']}; min-width: 40px;")
        layout.addWidget(self._zoom_label)
        
        zoom_in = QPushButton("+")
        zoom_in.setToolTip("Увеличить")
        zoom_in.clicked.connect(lambda: self.set_zoom(self._zoom * 1.25))
        layout.addWidget(zoom_in)
        
        layout.addStretch()
        
        # Кнопки управления треками
        add_video = QPushButton("+ Видео")
        add_video.clicked.connect(lambda: self.add_track("Video", TrackType.VIDEO))
        layout.addWidget(add_video)
        
        add_audio = QPushButton("+ Аудио")
        add_audio.clicked.connect(lambda: self.add_track("Audio", TrackType.AUDIO))
        layout.addWidget(add_audio)
        
        return toolbar
    
    def _create_default_tracks(self) -> None:
        """Создать треки по умолчанию."""
        self.add_track("Video 1", TrackType.VIDEO)
        self.add_track("Audio 1", TrackType.AUDIO)
    
    def add_track(self, name: str, track_type: TrackType) -> Track:
        """Добавить новый трек."""
        track = Track(
            id=f"track_{len(self._tracks)}",
            name=name,
            track_type=track_type,
        )
        self._tracks.append(track)
        
        # Добавляем лейбл
        label = QLabel(f"  {name}")
        label.setFixedHeight(track.height)
        label.setStyleSheet(f"""
            background-color: {COLORS['bg_tertiary'] if track_type == TrackType.VIDEO else COLORS['bg_secondary']};
            color: {COLORS['text_primary']};
            border-bottom: 1px solid {COLORS['border']};
        """)
        self._track_labels_layout.addWidget(label)
        
        # Добавляем виджет трека
        track_widget = TimelineTrackWidget(track)
        track_widget.set_zoom(self._zoom)
        track_widget.clip_selected.connect(lambda c: self.clip_selected.emit(c))
        self._track_widgets.append(track_widget)
        self._tracks_layout.addWidget(track_widget)
        
        return track
    
    def add_clip(self, track_index: int, clip: Clip) -> None:
        """Добавить клип на трек."""
        if 0 <= track_index < len(self._tracks):
            self._tracks[track_index].clips.append(clip)
            self._track_widgets[track_index].update()
    
    def set_zoom(self, zoom: float) -> None:
        """Установить масштаб."""
        self._zoom = max(0.1, min(zoom, 10.0))
        self._zoom_label.setText(f"{int(self._zoom * 100)}%")
        
        self._ruler.set_zoom(self._zoom)
        for widget in self._track_widgets:
            widget.set_zoom(self._zoom)
    
    def set_playhead(self, position_ms: int) -> None:
        """Установить позицию playhead."""
        self._playhead_position = position_ms
        self.update()
    
    def wheelEvent(self, event: QWheelEvent) -> None:
        """Масштабирование колесом мыши с Ctrl."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.set_zoom(self._zoom * 1.1)
            else:
                self.set_zoom(self._zoom * 0.9)
            event.accept()
        else:
            super().wheelEvent(event)

