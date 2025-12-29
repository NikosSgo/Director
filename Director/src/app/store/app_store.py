"""Реактивный store приложения с RxPY."""

from dataclasses import replace
from typing import Callable

from reactivex import Observable, operators as ops, of, create
from reactivex.subject import BehaviorSubject, Subject
from reactivex.disposable import CompositeDisposable

from app.api import GatewayClient
from app.models.project import AppState, Project, ProjectState, StorageInfo
from app.store.actions import Action, ActionType


class AppStore:
    """
    Центральный реактивный store приложения.
    
    Работает через единый API Gateway.
    """

    def __init__(self, gateway: GatewayClient):
        self._gateway = gateway
        self._disposables = CompositeDisposable()

        # Начальное состояние
        initial_state = AppState()

        self._state_subject = BehaviorSubject(initial_state)
        self._actions_subject = Subject()

        self._setup_reducer()
        self._setup_effects()

    @property
    def gateway(self) -> GatewayClient:
        """Клиент API Gateway."""
        return self._gateway

    @property
    def state_stream(self) -> Observable[AppState]:
        """Observable текущего состояния."""
        return self._state_subject.pipe(ops.distinct_until_changed())

    @property
    def state(self) -> AppState:
        """Текущее состояние."""
        return self._state_subject.value

    def dispatch(self, action: Action) -> None:
        """Отправить действие."""
        self._actions_subject.on_next(action)

    def select(self, selector: Callable[[AppState], any]) -> Observable:
        """Выбрать часть состояния."""
        return self.state_stream.pipe(
            ops.map(selector),
            ops.distinct_until_changed(),
        )

    def dispose(self) -> None:
        """Освободить ресурсы."""
        self._disposables.dispose()
        self._state_subject.dispose()
        self._actions_subject.dispose()
        self._gateway.disconnect()

    def _setup_reducer(self) -> None:
        """Настроить редьюсер."""

        def reducer(state: AppState, action: Action) -> AppState:
            match action.type:
                # Connection
                case ActionType.CONNECT_REQUEST:
                    return replace(state, is_loading=True, error_message=None)

                case ActionType.CONNECT_SUCCESS:
                    return replace(
                        state,
                        engine_connected=True,
                        file_gateway_connected=True,
                        is_loading=False,
                    )

                case ActionType.CONNECT_FAILURE:
                    return replace(
                        state,
                        engine_connected=False,
                        file_gateway_connected=False,
                        is_loading=False,
                        error_message=action.error,
                    )

                # Services info
                case ActionType.GET_SERVICES_INFO_SUCCESS:
                    info = action.payload
                    storage_info = StorageInfo(
                        storage_id=info.get("storage_id", ""),
                        hostname=info.get("storage_hostname", ""),
                        os=info.get("storage_os", ""),
                        home_directory=info.get("home_directory", ""),
                        default_projects_path=info.get("default_projects_path", ""),
                        root_paths=tuple(info.get("root_paths", [])),
                        total_space=info.get("total_space", 0),
                        free_space=info.get("free_space", 0),
                    )
                    return replace(state, storage_info=storage_info)

                # Load projects
                case ActionType.LOAD_PROJECTS_REQUEST:
                    return replace(state, is_loading=True, error_message=None)

                case ActionType.LOAD_PROJECTS_SUCCESS:
                    projects = tuple(action.payload) if action.payload else ()
                    return replace(state, projects=projects, is_loading=False)

                case ActionType.LOAD_PROJECTS_FAILURE:
                    return replace(state, is_loading=False, error_message=action.error)

                # Create project
                case ActionType.CREATE_PROJECT_REQUEST:
                    return replace(state, is_loading=True, error_message=None)

                case ActionType.CREATE_PROJECT_SUCCESS:
                    project: Project = action.payload
                    new_projects = (*state.projects, project)
                    return replace(
                        state,
                        projects=new_projects,
                        current_project=project,
                        project_state=ProjectState.OPEN,
                        is_loading=False,
                    )

                case ActionType.CREATE_PROJECT_FAILURE:
                    return replace(state, is_loading=False, error_message=action.error)

                # Open project
                case ActionType.OPEN_PROJECT_REQUEST:
                    return replace(state, project_state=ProjectState.LOADING, is_loading=True, error_message=None)

                case ActionType.OPEN_PROJECT_SUCCESS:
                    project: Project = action.payload
                    updated_projects = tuple(
                        project if p.id == project.id else p for p in state.projects
                    )
                    return replace(
                        state,
                        projects=updated_projects,
                        current_project=project,
                        project_state=ProjectState.OPEN,
                        is_loading=False,
                    )

                case ActionType.OPEN_PROJECT_FAILURE:
                    return replace(state, project_state=ProjectState.ERROR, is_loading=False, error_message=action.error)

                # Delete project
                case ActionType.DELETE_PROJECT_REQUEST:
                    return replace(state, is_loading=True, error_message=None)

                case ActionType.DELETE_PROJECT_SUCCESS:
                    project_id = action.payload
                    new_projects = tuple(p for p in state.projects if p.id != project_id)
                    return replace(state, projects=new_projects, is_loading=False)

                case ActionType.DELETE_PROJECT_FAILURE:
                    return replace(state, is_loading=False, error_message=action.error)

                # Close project
                case ActionType.CLOSE_PROJECT:
                    return replace(state, current_project=None, project_state=ProjectState.CLOSED)

                # Browse directory
                case ActionType.BROWSE_DIRECTORY_SUCCESS:
                    result = action.payload
                    return replace(
                        state,
                        current_browsed_path=result.get("current_path", ""),
                        browsed_entries=tuple(result.get("entries", [])),
                    )

                # Clear error
                case ActionType.CLEAR_ERROR:
                    return replace(state, error_message=None)

                case _:
                    return state

        subscription = self._actions_subject.pipe(
            ops.scan(reducer, self._state_subject.value),
        ).subscribe(self._state_subject.on_next)

        self._disposables.add(subscription)

    def _setup_effects(self) -> None:
        """Настроить эффекты."""

        def make_observable(func):
            """Обернуть синхронный вызов в Observable."""
            def wrapper(*args, **kwargs):
                def subscribe(observer, scheduler=None):
                    try:
                        result = func(*args, **kwargs)
                        observer.on_next(result)
                        observer.on_completed()
                    except Exception as e:
                        observer.on_error(e)
                return create(subscribe)
            return wrapper

        # Connect effect
        connect_effect = self._actions_subject.pipe(
            ops.filter(lambda a: a.type == ActionType.CONNECT_REQUEST),
            ops.flat_map(lambda _: make_observable(self._gateway.connect)()),
        ).subscribe(
            on_next=lambda success: self.dispatch(
                Action.connect_success() if success else Action.connect_failure("Не удалось подключиться к API Gateway")
            ),
            on_error=lambda e: self.dispatch(Action.connect_failure(str(e))),
        )
        self._disposables.add(connect_effect)

        # After connect - get services info and load projects
        after_connect = self._actions_subject.pipe(
            ops.filter(lambda a: a.type == ActionType.CONNECT_SUCCESS),
            ops.flat_map(lambda _: make_observable(self._get_services_info)()),
        ).subscribe(
            on_next=lambda info: (
                self.dispatch(Action.get_services_info_success(info)),
                self.dispatch(Action.load_projects_request()),
            ),
            on_error=lambda e: print(f"[Services Info Error] {e}"),
        )
        self._disposables.add(after_connect)

        # Load projects effect
        load_projects_effect = self._actions_subject.pipe(
            ops.filter(lambda a: a.type == ActionType.LOAD_PROJECTS_REQUEST),
            ops.flat_map(lambda _: make_observable(self._list_projects)()),
        ).subscribe(
            on_next=lambda projects: self.dispatch(Action.load_projects_success(projects)),
            on_error=lambda e: self.dispatch(Action.load_projects_failure(str(e))),
        )
        self._disposables.add(load_projects_effect)

        # Create project effect
        create_project_effect = self._actions_subject.pipe(
            ops.filter(lambda a: a.type == ActionType.CREATE_PROJECT_REQUEST),
            ops.flat_map(lambda a: make_observable(self._create_project)(a.payload["name"], a.payload["path"])),
        ).subscribe(
            on_next=lambda project: self.dispatch(Action.create_project_success(project)),
            on_error=lambda e: self.dispatch(Action.create_project_failure(str(e))),
        )
        self._disposables.add(create_project_effect)

        # Open project effect
        open_project_effect = self._actions_subject.pipe(
            ops.filter(lambda a: a.type == ActionType.OPEN_PROJECT_REQUEST),
            ops.flat_map(lambda a: make_observable(self._open_project)(a.payload)),
        ).subscribe(
            on_next=lambda project: self.dispatch(Action.open_project_success(project)),
            on_error=lambda e: self.dispatch(Action.open_project_failure(str(e))),
        )
        self._disposables.add(open_project_effect)

        # Delete project effect
        delete_project_effect = self._actions_subject.pipe(
            ops.filter(lambda a: a.type == ActionType.DELETE_PROJECT_REQUEST),
            ops.flat_map(lambda a: make_observable(self._delete_project)(a.payload["id"], a.payload["delete_files"])),
        ).subscribe(
            on_next=lambda project_id: self.dispatch(Action.delete_project_success(project_id)),
            on_error=lambda e: self.dispatch(Action.delete_project_failure(str(e))),
        )
        self._disposables.add(delete_project_effect)

        # Browse directory effect
        browse_effect = self._actions_subject.pipe(
            ops.filter(lambda a: a.type == ActionType.BROWSE_DIRECTORY_REQUEST),
            ops.flat_map(lambda a: make_observable(self._browse_directory)(a.payload)),
        ).subscribe(
            on_next=lambda result: self.dispatch(Action.browse_directory_success(result)),
            on_error=lambda e: self.dispatch(Action.browse_directory_failure(str(e))),
        )
        self._disposables.add(browse_effect)

    # === Gateway call wrappers ===

    def _get_services_info(self) -> dict:
        """Получить информацию о сервисах."""
        response = self._gateway.get_services_info()
        return {
            "gateway_version": response.gateway_version,
            "engine_hostname": response.engine_hostname,
            "storage_hostname": response.storage_hostname,
            "storage_os": response.storage_os,
            "home_directory": response.home_directory,
            "default_projects_path": response.default_projects_path,
            "root_paths": list(response.root_paths),
            "total_space": response.total_space,
            "free_space": response.free_space,
        }

    def _list_projects(self) -> list[Project]:
        """Получить список проектов."""
        response = self._gateway.list_projects()
        return [
            Project(
                id=p.id,
                name=p.name,
                path=p.path,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in response.projects
        ]

    def _create_project(self, name: str, path: str) -> Project:
        """Создать проект."""
        response = self._gateway.create_project(name, path)
        if not response.success:
            raise Exception(response.error_message)
        p = response.project
        return Project(
            id=p.id,
            name=p.name,
            path=p.path,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )

    def _open_project(self, project_id: str) -> Project:
        """Открыть проект."""
        response = self._gateway.open_project(project_id)
        if not response.success:
            raise Exception(response.error_message)
        p = response.project
        return Project(
            id=p.id,
            name=p.name,
            path=p.path,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )

    def _delete_project(self, project_id: str, delete_files: bool) -> str:
        """Удалить проект."""
        response = self._gateway.delete_project(project_id, delete_files)
        if not response.success:
            raise Exception(response.error_message)
        return project_id

    def _browse_directory(self, path: str) -> dict:
        """Просмотреть директорию."""
        response = self._gateway.browse_directory(path)
        if not response.success:
            raise Exception(response.error_message)
        return {
            "current_path": response.current_path,
            "parent_path": response.parent_path,
            "entries": [
                {
                    "name": e.name,
                    "path": e.path,
                    "is_directory": e.is_directory,
                    "size": e.size,
                }
                for e in response.entries
            ],
        }
