"""Actions для управления состоянием приложения."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Optional

from app.models.project import EngineInfo, Project, StorageInfo


class ActionType(Enum):
    """Типы действий."""

    # Подключение к Engine
    CONNECT_ENGINE_REQUEST = auto()
    CONNECT_ENGINE_SUCCESS = auto()
    CONNECT_ENGINE_FAILURE = auto()

    # Подключение к FileGateway
    CONNECT_FILE_GATEWAY_REQUEST = auto()
    CONNECT_FILE_GATEWAY_SUCCESS = auto()
    CONNECT_FILE_GATEWAY_FAILURE = auto()

    # Информация о движке
    GET_ENGINE_INFO_SUCCESS = auto()

    # Информация о хранилище
    GET_STORAGE_INFO_SUCCESS = auto()

    # Проекты - загрузка списка
    LOAD_PROJECTS_REQUEST = auto()
    LOAD_PROJECTS_SUCCESS = auto()
    LOAD_PROJECTS_FAILURE = auto()

    # Проекты - создание
    CREATE_PROJECT_REQUEST = auto()
    CREATE_PROJECT_SUCCESS = auto()
    CREATE_PROJECT_FAILURE = auto()

    # Проекты - открытие
    OPEN_PROJECT_REQUEST = auto()
    OPEN_PROJECT_SUCCESS = auto()
    OPEN_PROJECT_FAILURE = auto()

    # Проекты - удаление
    DELETE_PROJECT_REQUEST = auto()
    DELETE_PROJECT_SUCCESS = auto()
    DELETE_PROJECT_FAILURE = auto()

    # Проекты - закрытие
    CLOSE_PROJECT = auto()

    # Очистка ошибок
    CLEAR_ERROR = auto()


@dataclass(frozen=True)
class Action:
    """Неизменяемое действие."""

    type: ActionType
    payload: Any = None
    error: Optional[str] = None

    # Engine connection
    @staticmethod
    def connect_engine_request() -> "Action":
        return Action(ActionType.CONNECT_ENGINE_REQUEST)

    @staticmethod
    def connect_engine_success() -> "Action":
        return Action(ActionType.CONNECT_ENGINE_SUCCESS)

    @staticmethod
    def connect_engine_failure(error: str) -> "Action":
        return Action(ActionType.CONNECT_ENGINE_FAILURE, error=error)

    # FileGateway connection
    @staticmethod
    def connect_file_gateway_request() -> "Action":
        return Action(ActionType.CONNECT_FILE_GATEWAY_REQUEST)

    @staticmethod
    def connect_file_gateway_success() -> "Action":
        return Action(ActionType.CONNECT_FILE_GATEWAY_SUCCESS)

    @staticmethod
    def connect_file_gateway_failure(error: str) -> "Action":
        return Action(ActionType.CONNECT_FILE_GATEWAY_FAILURE, error=error)

    # Info
    @staticmethod
    def get_engine_info_success(info: EngineInfo) -> "Action":
        return Action(ActionType.GET_ENGINE_INFO_SUCCESS, payload=info)

    @staticmethod
    def get_storage_info_success(info: StorageInfo) -> "Action":
        return Action(ActionType.GET_STORAGE_INFO_SUCCESS, payload=info)

    # Projects
    @staticmethod
    def load_projects_request() -> "Action":
        return Action(ActionType.LOAD_PROJECTS_REQUEST)

    @staticmethod
    def load_projects_success(projects: list[Project]) -> "Action":
        return Action(ActionType.LOAD_PROJECTS_SUCCESS, payload=projects)

    @staticmethod
    def load_projects_failure(error: str) -> "Action":
        return Action(ActionType.LOAD_PROJECTS_FAILURE, error=error)

    @staticmethod
    def create_project_request(name: str, path: str) -> "Action":
        return Action(ActionType.CREATE_PROJECT_REQUEST, payload={"name": name, "path": path})

    @staticmethod
    def create_project_success(project: Project) -> "Action":
        return Action(ActionType.CREATE_PROJECT_SUCCESS, payload=project)

    @staticmethod
    def create_project_failure(error: str) -> "Action":
        return Action(ActionType.CREATE_PROJECT_FAILURE, error=error)

    @staticmethod
    def open_project_request(project_id: str) -> "Action":
        return Action(ActionType.OPEN_PROJECT_REQUEST, payload=project_id)

    @staticmethod
    def open_project_success(project: Project) -> "Action":
        return Action(ActionType.OPEN_PROJECT_SUCCESS, payload=project)

    @staticmethod
    def open_project_failure(error: str) -> "Action":
        return Action(ActionType.OPEN_PROJECT_FAILURE, error=error)

    @staticmethod
    def delete_project_request(project_id: str) -> "Action":
        return Action(ActionType.DELETE_PROJECT_REQUEST, payload=project_id)

    @staticmethod
    def delete_project_success(project_id: str) -> "Action":
        return Action(ActionType.DELETE_PROJECT_SUCCESS, payload=project_id)

    @staticmethod
    def delete_project_failure(error: str) -> "Action":
        return Action(ActionType.DELETE_PROJECT_FAILURE, error=error)

    @staticmethod
    def close_project() -> "Action":
        return Action(ActionType.CLOSE_PROJECT)

    @staticmethod
    def clear_error() -> "Action":
        return Action(ActionType.CLEAR_ERROR)
