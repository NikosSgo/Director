"""Компонент таймлайна для редактирования видео."""

from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum, auto

from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QMouseEvent, QWheelEvent, QCursor
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QLabel,
    QPushButton,
    QSizePolicy,
    QMenu,
    QInputDialog,
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


class TrimHandle(Enum):
    """Тип ручки обрезки."""
    NONE = auto()
    LEFT = auto()
    RIGHT = auto()


class TimelineTrackWidget(QWidget):
    """Виджет одного трека."""
    
    clip_selected = pyqtSignal(Clip)
    clip_moved = pyqtSignal(Clip, int)  # клип, новая позиция
    clip_trimmed = pyqtSignal(Clip, int, int)  # клип, новый in_point, новый out_point
    clip_deleted = pyqtSignal(Clip)  # клип удалён
    clip_split = pyqtSignal(Clip, int)  # клип, позиция разреза (мс)
    
    TRIM_HANDLE_WIDTH = 8  # ширина ручки обрезки в пикселях
    
    def __init__(self, track: Track, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._track = track
        self._zoom = 1.0
        self._offset = 0
        self._selected_clip: Optional[Clip] = None
        self._dragging = False
        self._drag_start_x = 0
        self._drag_clip_start = 0
        
        # Для обрезки
        self._trimming = False
        self._trim_handle = TrimHandle.NONE
        self._trim_clip: Optional[Clip] = None
        self._trim_original_start = 0
        self._trim_original_duration = 0
        
        self.setFixedHeight(track.height)
        self.setMinimumWidth(200)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
    
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
    
    def _get_trim_handle(self, x: int, clip: Clip) -> TrimHandle:
        """Определить ручку обрезки."""
        clip_x = self._time_to_x(clip.start_time)
        clip_end_x = self._time_to_x(clip.end_time)
        
        if abs(x - clip_x) <= self.TRIM_HANDLE_WIDTH:
            return TrimHandle.LEFT
        elif abs(x - clip_end_x) <= self.TRIM_HANDLE_WIDTH:
            return TrimHandle.RIGHT
        return TrimHandle.NONE
    
    def _show_context_menu(self, pos) -> None:
        """Контекстное меню для клипа."""
        clip = self._clip_at(pos.x())
        if not clip:
            return
        
        self._selected_clip = clip
        self.clip_selected.emit(clip)
        self.update()
        
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLORS['bg_secondary']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 20px;
            }}
            QMenu::item:selected {{
                background-color: {COLORS['bg_hover']};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {COLORS['border']};
                margin: 4px 0;
            }}
        """)
        
        # Разрезать здесь
        split_action = menu.addAction("✂ Разрезать здесь")
        split_pos = self._x_to_time(pos.x())
        split_action.triggered.connect(lambda: self.clip_split.emit(clip, split_pos))
        
        menu.addSeparator()
        
        # Удалить
        delete_action = menu.addAction("🗑 Удалить")
        delete_action.triggered.connect(lambda: self._delete_clip(clip))
        
        menu.exec(self.mapToGlobal(pos))
    
    def _delete_clip(self, clip: Clip) -> None:
        """Удалить клип."""
        if clip in self._track.clips:
            self._track.clips.remove(clip)
            if self._selected_clip == clip:
                self._selected_clip = None
            self.clip_deleted.emit(clip)
            self.update()
    
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
            x = int(event.position().x())
            clip = self._clip_at(x)
            
            if clip:
                self._selected_clip = clip
                self.clip_selected.emit(clip)
                
                # Проверяем ручки обрезки
                handle = self._get_trim_handle(x, clip)
                if handle != TrimHandle.NONE:
                    self._trimming = True
                    self._trim_handle = handle
                    self._trim_clip = clip
                    self._trim_original_start = clip.start_time
                    self._trim_original_duration = clip.duration
                    self._drag_start_x = x
                else:
                    # Обычное перетаскивание
                    self._dragging = True
                    self._drag_start_x = x
                    self._drag_clip_start = clip.start_time
                
                self.update()
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        x = int(event.position().x())
        
        # Обновляем курсор
        clip = self._clip_at(x)
        if clip:
            handle = self._get_trim_handle(x, clip)
            if handle != TrimHandle.NONE:
                self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        
        # Обрезка
        if self._trimming and self._trim_clip:
            dx_time = self._x_to_time(x) - self._x_to_time(self._drag_start_x)
            
            if self._trim_handle == TrimHandle.LEFT:
                # Обрезка слева - меняем start_time и duration
                new_start = max(0, self._trim_original_start + dx_time)
                duration_change = self._trim_original_start - new_start
                new_duration = max(500, self._trim_original_duration + duration_change)  # мин 0.5 сек
                
                # Обновляем клип в треке
                for i, c in enumerate(self._track.clips):
                    if c.id == self._trim_clip.id:
                        self._track.clips[i] = Clip(
                            id=c.id,
                            name=c.name,
                            file_path=c.file_path,
                            track_index=c.track_index,
                            start_time=new_start,
                            duration=new_duration,
                            in_point=c.in_point + (self._trim_original_start - new_start),
                            out_point=c.out_point,
                            color=c.color,
                        )
                        self._trim_clip = self._track.clips[i]
                        break
                        
            elif self._trim_handle == TrimHandle.RIGHT:
                # Обрезка справа - меняем только duration
                new_duration = max(500, self._trim_original_duration + dx_time)  # мин 0.5 сек
                
                for i, c in enumerate(self._track.clips):
                    if c.id == self._trim_clip.id:
                        self._track.clips[i] = Clip(
                            id=c.id,
                            name=c.name,
                            file_path=c.file_path,
                            track_index=c.track_index,
                            start_time=c.start_time,
                            duration=new_duration,
                            in_point=c.in_point,
                            out_point=c.in_point + new_duration,
                            color=c.color,
                        )
                        self._trim_clip = self._track.clips[i]
                        break
            
            self.update()
            return
        
        # Перетаскивание
        if self._dragging and self._selected_clip:
            dx = x - self._drag_start_x
            new_time = max(0, self._drag_clip_start + self._x_to_time(dx) - self._x_to_time(0))
            
            # Обновляем клип в треке
            for i, c in enumerate(self._track.clips):
                if c.id == self._selected_clip.id:
                    self._track.clips[i] = Clip(
                        id=c.id,
                        name=c.name,
                        file_path=c.file_path,
                        track_index=c.track_index,
                        start_time=new_time,
                        duration=c.duration,
                        in_point=c.in_point,
                        out_point=c.out_point,
                        color=c.color,
                    )
                    self._selected_clip = self._track.clips[i]
                    break
            self.update()
    
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._trimming and self._trim_clip:
            self.clip_trimmed.emit(
                self._trim_clip,
                self._trim_clip.in_point,
                self._trim_clip.out_point
            )
        elif self._dragging and self._selected_clip:
            self.clip_moved.emit(self._selected_clip, self._selected_clip.start_time)
        
        self._dragging = False
        self._trimming = False
        self._trim_handle = TrimHandle.NONE
        self._trim_clip = None


class Timeline(QWidget):
    """Главный виджет таймлайна."""
    
    position_changed = pyqtSignal(int)  # мс
    clip_selected = pyqtSignal(object)  # Clip or None
    clip_deleted = pyqtSignal(object)  # Clip
    clip_changed = pyqtSignal()  # any clip changed (for auto-save)
    
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
        track_widget.clip_deleted.connect(self._on_clip_deleted)
        track_widget.clip_split.connect(self._on_clip_split)
        track_widget.clip_moved.connect(lambda c, t: self.clip_changed.emit())
        track_widget.clip_trimmed.connect(lambda c, i, o: self.clip_changed.emit())
        self._track_widgets.append(track_widget)
        self._tracks_layout.addWidget(track_widget)
        
        return track
    
    def _on_clip_deleted(self, clip: Clip) -> None:
        """Обработка удаления клипа."""
        self.clip_deleted.emit(clip)
        self.clip_changed.emit()
    
    def _on_clip_split(self, clip: Clip, split_time: int) -> None:
        """Разрезать клип в указанной позиции."""
        # Находим трек с клипом
        for track_idx, track in enumerate(self._tracks):
            for i, c in enumerate(track.clips):
                if c.id == clip.id:
                    # Проверяем что разрез внутри клипа
                    if clip.start_time < split_time < clip.end_time:
                        # Создаём два новых клипа
                        first_duration = split_time - clip.start_time
                        second_duration = clip.duration - first_duration
                        
                        # Первая часть (изменяем оригинал)
                        first_clip = Clip(
                            id=clip.id,
                            name=clip.name,
                            file_path=clip.file_path,
                            track_index=clip.track_index,
                            start_time=clip.start_time,
                            duration=first_duration,
                            in_point=clip.in_point,
                            out_point=clip.in_point + first_duration,
                            color=clip.color,
                        )
                        
                        # Вторая часть (новый клип)
                        second_clip = Clip(
                            id=f"{clip.id}_split",
                            name=f"{clip.name} (2)",
                            file_path=clip.file_path,
                            track_index=clip.track_index,
                            start_time=split_time,
                            duration=second_duration,
                            in_point=clip.in_point + first_duration,
                            out_point=clip.out_point,
                            color=clip.color,
                        )
                        
                        # Заменяем и добавляем
                        track.clips[i] = first_clip
                        track.clips.insert(i + 1, second_clip)
                        
                        self._track_widgets[track_idx].update()
                        self.clip_changed.emit()
                    return
    
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
    
    def get_all_clips(self) -> List[Clip]:
        """Получить все клипы со всех треков."""
        clips = []
        for track in self._tracks:
            clips.extend(track.clips)
        return clips
    
    def remove_clip(self, clip_id: str) -> None:
        """Удалить клип по ID."""
        for track_idx, track in enumerate(self._tracks):
            for clip in track.clips:
                if clip.id == clip_id:
                    track.clips.remove(clip)
                    self._track_widgets[track_idx].update()
                    self.clip_changed.emit()
                    return
    
    def clear_tracks(self) -> None:
        """Очистить все треки."""
        for track in self._tracks:
            track.clips.clear()
        for widget in self._track_widgets:
            widget.update()
    
    def load_clips(self, clips_data: List[dict]) -> None:
        """Загрузить клипы из данных."""
        self.clear_tracks()
        
        for data in clips_data:
            try:
                track_idx = data.get("track_index", 0)
                
                # Убеждаемся что трек существует
                while len(self._tracks) <= track_idx:
                    track_type = TrackType.VIDEO if track_idx % 2 == 0 else TrackType.AUDIO
                    self.add_track(f"Track {track_idx + 1}", track_type)
                
                clip = Clip(
                    id=data["id"],
                    name=data["name"],
                    file_path=data["file_path"],
                    track_index=track_idx,
                    start_time=data.get("start_time", 0),
                    duration=data.get("duration", 1000),
                    in_point=data.get("in_point", 0),
                    out_point=data.get("out_point", 0),
                    color=data.get("color", COLORS['accent']),
                )
                
                self._tracks[track_idx].clips.append(clip)
                
            except (KeyError, ValueError) as e:
                print(f"[Timeline] Clip load error: {e}")
        
        # Обновляем виджеты
        for widget in self._track_widgets:
            widget.update()
    
    def get_clips_data(self) -> List[dict]:
        """Получить данные клипов для сохранения."""
        clips_data = []
        for clip in self.get_all_clips():
            clips_data.append({
                "id": clip.id,
                "name": clip.name,
                "file_path": clip.file_path,
                "track_index": clip.track_index,
                "start_time": clip.start_time,
                "duration": clip.duration,
                "in_point": clip.in_point,
                "out_point": clip.out_point,
                "color": clip.color,
            })
        return clips_data

