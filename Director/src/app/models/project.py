"""Модели данных проекта."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional


class ProjectState(Enum):
    """Состояние проекта."""

    CLOSED = auto()
    LOADING = auto()
    OPEN = auto()
    ERROR = auto()


@dataclass(frozen=True)
class Project:
    """Неизменяемая модель проекта."""

    id: str
    name: str
    path: str
    created_at: int  # Unix timestamp
    updated_at: int  # Unix timestamp

    @property
    def created_datetime(self) -> datetime:
        """Дата создания."""
        return datetime.fromtimestamp(self.created_at)

    @property
    def updated_datetime(self) -> datetime:
        """Дата обновления."""
        return datetime.fromtimestamp(self.updated_at)


@dataclass(frozen=True)
class EngineInfo:
    """Информация о движке обработки."""

    engine_id: str
    version: str
    supported_formats: tuple[str, ...]

    @classmethod
    def from_proto(cls, proto) -> "EngineInfo":
        """Создать из protobuf сообщения."""
        return cls(
            engine_id=proto.engine_id,
            version=proto.version,
            supported_formats=tuple(proto.supported_formats),
        )


@dataclass(frozen=True)
class StorageInfo:
    """Информация о файловом хранилище."""

    storage_id: str
    hostname: str
    os: str
    home_directory: str
    default_projects_path: str
    root_paths: tuple[str, ...]
    total_space: int
    free_space: int

    @classmethod
    def from_proto(cls, proto) -> "StorageInfo":
        """Создать из protobuf сообщения."""
        return cls(
            storage_id=proto.storage_id,
            hostname=proto.hostname,
            os=proto.os,
            home_directory=proto.home_directory,
            default_projects_path=proto.default_projects_path,
            root_paths=tuple(proto.root_paths),
            total_space=proto.total_space,
            free_space=proto.free_space,
        )

    @property
    def free_space_gb(self) -> float:
        """Свободное место в ГБ."""
        return self.free_space / (1024 ** 3)

    @property
    def total_space_gb(self) -> float:
        """Общий размер в ГБ."""
        return self.total_space / (1024 ** 3)


@dataclass(frozen=True)
class DirectoryEntry:
    """Элемент директории."""

    name: str
    path: str
    is_directory: bool
    size: int
    created_at: datetime
    modified_at: datetime
    mime_type: str = ""

    @classmethod
    def from_file_gateway_proto(cls, proto) -> "DirectoryEntry":
        """Создать из protobuf сообщения FileGateway."""
        return cls(
            name=proto.name,
            path=proto.path,
            is_directory=proto.is_directory,
            size=proto.size,
            created_at=datetime.fromtimestamp(proto.created_at) if proto.created_at else datetime.now(),
            modified_at=datetime.fromtimestamp(proto.modified_at) if proto.modified_at else datetime.now(),
            mime_type=proto.mime_type,
        )


@dataclass(frozen=True)
class DirectoryListing:
    """Содержимое директории."""

    current_path: str
    parent_path: str
    entries: tuple[DirectoryEntry, ...]

    @classmethod
    def from_file_gateway_proto(cls, proto) -> "DirectoryListing":
        """Создать из protobuf сообщения FileGateway."""
        return cls(
            current_path=proto.current_path,
            parent_path=proto.parent_path,
            entries=tuple(DirectoryEntry.from_file_gateway_proto(e) for e in proto.entries),
        )


@dataclass(frozen=True)
class AppState:
    """Глобальное состояние приложения (неизменяемое)."""

    # Проекты
    projects: tuple[Project, ...] = field(default_factory=tuple)
    current_project: Optional[Project] = None
    project_state: ProjectState = ProjectState.CLOSED

    # Статус
    is_loading: bool = False
    error_message: Optional[str] = None

    # Подключения
    engine_connected: bool = False
    file_gateway_connected: bool = False

    # Информация о сервисах
    engine_info: Optional[EngineInfo] = None
    storage_info: Optional[StorageInfo] = None

    # Навигация по файловой системе
    current_browsed_path: str = ""
    browsed_entries: tuple = field(default_factory=tuple)
