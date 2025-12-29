"""Actions для управления состоянием приложения."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Optional

from app.models.project import EngineInfo, Project, StorageInfo


class ActionType(Enum):
    """Типы действий."""

    # Подключение к API Gateway
    CONNECT_REQUEST = auto()
    CONNECT_SUCCESS = auto()
    CONNECT_FAILURE = auto()

    # Информация о сервисах
    GET_SERVICES_INFO_SUCCESS = auto()

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

    # Файловая система - навигация
    BROWSE_DIRECTORY_REQUEST = auto()
    BROWSE_DIRECTORY_SUCCESS = auto()
    BROWSE_DIRECTORY_FAILURE = auto()

    # Очистка ошибок
    CLEAR_ERROR = auto()


@dataclass(frozen=True)
class Action:
    """Неизменяемое действие."""

    type: ActionType
    payload: Any = None
    error: Optional[str] = None

    # === Connection ===
    
    @staticmethod
    def connect_request() -> "Action":
        return Action(ActionType.CONNECT_REQUEST)

    @staticmethod
    def connect_success() -> "Action":
        return Action(ActionType.CONNECT_SUCCESS)

    @staticmethod
    def connect_failure(error: str) -> "Action":
        return Action(ActionType.CONNECT_FAILURE, error=error)

    # === Services Info ===
    
    @staticmethod
    def get_services_info_success(info: dict) -> "Action":
        return Action(ActionType.GET_SERVICES_INFO_SUCCESS, payload=info)

    # === Projects ===
    
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
    def delete_project_request(project_id: str, delete_files: bool = False) -> "Action":
        return Action(ActionType.DELETE_PROJECT_REQUEST, payload={"id": project_id, "delete_files": delete_files})

    @staticmethod
    def delete_project_success(project_id: str) -> "Action":
        return Action(ActionType.DELETE_PROJECT_SUCCESS, payload=project_id)

    @staticmethod
    def delete_project_failure(error: str) -> "Action":
        return Action(ActionType.DELETE_PROJECT_FAILURE, error=error)

    @staticmethod
    def close_project() -> "Action":
        return Action(ActionType.CLOSE_PROJECT)

    # === File System ===
    
    @staticmethod
    def browse_directory_request(path: str = "") -> "Action":
        return Action(ActionType.BROWSE_DIRECTORY_REQUEST, payload=path)

    @staticmethod
    def browse_directory_success(result: dict) -> "Action":
        return Action(ActionType.BROWSE_DIRECTORY_SUCCESS, payload=result)

    @staticmethod
    def browse_directory_failure(error: str) -> "Action":
        return Action(ActionType.BROWSE_DIRECTORY_FAILURE, error=error)

    # === Utils ===
    
    @staticmethod
    def clear_error() -> "Action":
        return Action(ActionType.CLEAR_ERROR)
