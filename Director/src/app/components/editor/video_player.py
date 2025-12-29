"""Компонент видеоплеера с превью."""

from typing import Optional
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStyle,
    QSizePolicy,
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

from app.utils.styles import COLORS


class VideoPlayer(QWidget):
    """Видеоплеер с базовыми контролами."""
    
    position_changed = pyqtSignal(int)  # миллисекунды
    duration_changed = pyqtSignal(int)  # миллисекунды
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_file: Optional[str] = None
        
        self._setup_ui()
        self._setup_player()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Видео виджет
        self._video_widget = QVideoWidget()
        self._video_widget.setStyleSheet(f"background-color: {COLORS['bg_dark']};")
        self._video_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._video_widget, stretch=1)
        
        # Контролы
        controls = self._create_controls()
        layout.addWidget(controls)
    
    def _create_controls(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_secondary']};
                border-top: 1px solid {COLORS['border']};
            }}
            QPushButton {{
                background: transparent;
                border: none;
                color: {COLORS['text_primary']};
                font-size: 16px;
                padding: 8px 12px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_hover']};
            }}
            QSlider::groove:horizontal {{
                height: 4px;
                background: {COLORS['bg_tertiary']};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 12px;
                height: 12px;
                background: {COLORS['accent']};
                border-radius: 6px;
                margin: -4px 0;
            }}
            QSlider::sub-page:horizontal {{
                background: {COLORS['accent']};
                border-radius: 2px;
            }}
        """)
        
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        
        # Прогресс бар
        self._progress_slider = QSlider(Qt.Orientation.Horizontal)
        self._progress_slider.setRange(0, 0)
        self._progress_slider.sliderMoved.connect(self._on_slider_moved)
        self._progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self._progress_slider.sliderReleased.connect(self._on_slider_released)
        layout.addWidget(self._progress_slider)
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(4)
        
        # Перемотка назад
        self._back_btn = QPushButton("⏮")
        self._back_btn.setToolTip("Назад 5 сек")
        self._back_btn.clicked.connect(lambda: self.seek_relative(-5000))
        buttons_layout.addWidget(self._back_btn)
        
        # Воспроизведение/Пауза
        self._play_btn = QPushButton("▶")
        self._play_btn.setToolTip("Воспроизвести")
        self._play_btn.clicked.connect(self.toggle_play)
        buttons_layout.addWidget(self._play_btn)
        
        # Стоп
        self._stop_btn = QPushButton("⏹")
        self._stop_btn.setToolTip("Стоп")
        self._stop_btn.clicked.connect(self.stop)
        buttons_layout.addWidget(self._stop_btn)
        
        # Перемотка вперёд
        self._forward_btn = QPushButton("⏭")
        self._forward_btn.setToolTip("Вперёд 5 сек")
        self._forward_btn.clicked.connect(lambda: self.seek_relative(5000))
        buttons_layout.addWidget(self._forward_btn)
        
        buttons_layout.addStretch()
        
        # Время
        self._time_label = QLabel("00:00 / 00:00")
        self._time_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        buttons_layout.addWidget(self._time_label)
        
        buttons_layout.addStretch()
        
        # Громкость
        self._volume_btn = QPushButton("🔊")
        self._volume_btn.setToolTip("Громкость")
        buttons_layout.addWidget(self._volume_btn)
        
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(70)
        self._volume_slider.setFixedWidth(80)
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        buttons_layout.addWidget(self._volume_slider)
        
        layout.addLayout(buttons_layout)
        
        return widget
    
    def _setup_player(self) -> None:
        self._player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._audio_output.setVolume(0.7)
        
        self._player.setAudioOutput(self._audio_output)
        self._player.setVideoOutput(self._video_widget)
        
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_state_changed)
        
        self._is_seeking = False
    
    def load(self, file_path: str) -> None:
        """Загрузить видео файл."""
        self._current_file = file_path
        self._player.setSource(QUrl.fromLocalFile(file_path))
    
    def play(self) -> None:
        """Воспроизвести."""
        self._player.play()
    
    def pause(self) -> None:
        """Пауза."""
        self._player.pause()
    
    def stop(self) -> None:
        """Остановить."""
        self._player.stop()
    
    def toggle_play(self) -> None:
        """Переключить воспроизведение/паузу."""
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.pause()
        else:
            self.play()
    
    def seek(self, position_ms: int) -> None:
        """Перейти к позиции (в миллисекундах)."""
        self._player.setPosition(position_ms)
    
    def seek_relative(self, offset_ms: int) -> None:
        """Относительная перемотка."""
        new_pos = self._player.position() + offset_ms
        new_pos = max(0, min(new_pos, self._player.duration()))
        self.seek(new_pos)
    
    @property
    def position(self) -> int:
        """Текущая позиция в мс."""
        return self._player.position()
    
    @property
    def duration(self) -> int:
        """Длительность в мс."""
        return self._player.duration()
    
    def _on_position_changed(self, position: int) -> None:
        if not self._is_seeking:
            self._progress_slider.setValue(position)
        self._update_time_label()
        self.position_changed.emit(position)
    
    def _on_duration_changed(self, duration: int) -> None:
        self._progress_slider.setRange(0, duration)
        self._update_time_label()
        self.duration_changed.emit(duration)
    
    def _on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._play_btn.setText("⏸")
            self._play_btn.setToolTip("Пауза")
        else:
            self._play_btn.setText("▶")
            self._play_btn.setToolTip("Воспроизвести")
    
    def _on_slider_pressed(self) -> None:
        self._is_seeking = True
    
    def _on_slider_released(self) -> None:
        self._is_seeking = False
        self.seek(self._progress_slider.value())
    
    def _on_slider_moved(self, position: int) -> None:
        self._update_time_label(position)
    
    def _on_volume_changed(self, value: int) -> None:
        volume = value / 100.0
        self._audio_output.setVolume(volume)
        
        if value == 0:
            self._volume_btn.setText("🔇")
        elif value < 30:
            self._volume_btn.setText("🔈")
        elif value < 70:
            self._volume_btn.setText("🔉")
        else:
            self._volume_btn.setText("🔊")
    
    def _update_time_label(self, current: Optional[int] = None) -> None:
        if current is None:
            current = self._player.position()
        total = self._player.duration()
        
        current_str = self._format_time(current)
        total_str = self._format_time(total)
        
        self._time_label.setText(f"{current_str} / {total_str}")
    
    @staticmethod
    def _format_time(ms: int) -> str:
        """Форматировать время из мс в MM:SS."""
        seconds = ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

