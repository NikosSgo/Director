"""Реактивный store приложения с RxPY."""

from dataclasses import replace
from typing import Callable

from reactivex import Observable, operators as ops
from reactivex.subject import BehaviorSubject, Subject
from reactivex.disposable import CompositeDisposable

from app.api import EngineClient, FileGatewayClient
from app.models.project import AppState, EngineInfo, Project, ProjectState, StorageInfo
from app.store.actions import Action, ActionType


class AppStore:
    """
    Центральный реактивный store приложения.
    
    Работает с двумя бэкендами:
    - EngineClient (DirectorEngine) - обработка видео, реестр проектов
    - FileGatewayClient (FileGateway) - файловые операции
    """

    def __init__(self, engine_client: EngineClient, file_gateway_client: FileGatewayClient):
        self._engine = engine_client
        self._file_gateway = file_gateway_client
        self._disposables = CompositeDisposable()

        # Начальное состояние
        initial_state = AppState()

        self._state_subject = BehaviorSubject(initial_state)
        self._actions_subject = Subject()

        self._setup_reducer()
        self._setup_effects()

    @property
    def engine(self) -> EngineClient:
        """Клиент DirectorEngine."""
        return self._engine

    @property
    def file_gateway(self) -> FileGatewayClient:
        """Клиент FileGateway."""
        return self._file_gateway

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
        self._engine.disconnect()
        self._file_gateway.disconnect()

    def _setup_reducer(self) -> None:
        """Настроить редьюсер."""

        def reducer(state: AppState, action: Action) -> AppState:
            match action.type:
                # Engine connection
                case ActionType.CONNECT_ENGINE_REQUEST:
                    return replace(state, is_loading=True, error_message=None)

                case ActionType.CONNECT_ENGINE_SUCCESS:
                    return replace(state, engine_connected=True, is_loading=False)

                case ActionType.CONNECT_ENGINE_FAILURE:
                    return replace(state, engine_connected=False, is_loading=False, error_message=action.error)

                # FileGateway connection
                case ActionType.CONNECT_FILE_GATEWAY_REQUEST:
                    return replace(state, is_loading=True, error_message=None)

                case ActionType.CONNECT_FILE_GATEWAY_SUCCESS:
                    return replace(state, file_gateway_connected=True, is_loading=False)

                case ActionType.CONNECT_FILE_GATEWAY_FAILURE:
                    return replace(state, file_gateway_connected=False, is_loading=False, error_message=action.error)

                # Info
                case ActionType.GET_ENGINE_INFO_SUCCESS:
                    return replace(state, engine_info=action.payload)

                case ActionType.GET_STORAGE_INFO_SUCCESS:
                    return replace(state, storage_info=action.payload)

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

        # Engine connection effect
        engine_connect_effect = self._actions_subject.pipe(
            ops.filter(lambda a: a.type == ActionType.CONNECT_ENGINE_REQUEST),
            ops.flat_map(lambda _: self._engine.connect()),
        ).subscribe(
            on_next=lambda success: self.dispatch(
                Action.connect_engine_success() if success else Action.connect_engine_failure("Не удалось подключиться к DirectorEngine")
            ),
            on_error=lambda e: self.dispatch(Action.connect_engine_failure(str(e))),
        )
        self._disposables.add(engine_connect_effect)

        # FileGateway connection effect
        file_gateway_connect_effect = self._actions_subject.pipe(
            ops.filter(lambda a: a.type == ActionType.CONNECT_FILE_GATEWAY_REQUEST),
            ops.flat_map(lambda _: self._file_gateway.connect()),
        ).subscribe(
            on_next=lambda success: self.dispatch(
                Action.connect_file_gateway_success() if success else Action.connect_file_gateway_failure("Не удалось подключиться к FileGateway")
            ),
            on_error=lambda e: self.dispatch(Action.connect_file_gateway_failure(str(e))),
        )
        self._disposables.add(file_gateway_connect_effect)

        # After engine connect - get info and load projects
        after_engine_connect = self._actions_subject.pipe(
            ops.filter(lambda a: a.type == ActionType.CONNECT_ENGINE_SUCCESS),
            ops.flat_map(lambda _: self._engine.get_engine_info()),
        ).subscribe(
            on_next=lambda info: (
                self.dispatch(Action.get_engine_info_success(info)),
                self.dispatch(Action.load_projects_request()),
            ),
            on_error=lambda e: print(f"[Engine Info Error] {e}"),
        )
        self._disposables.add(after_engine_connect)

        # After file gateway connect - get storage info
        after_file_gateway_connect = self._actions_subject.pipe(
            ops.filter(lambda a: a.type == ActionType.CONNECT_FILE_GATEWAY_SUCCESS),
            ops.flat_map(lambda _: self._file_gateway.get_storage_info()),
        ).subscribe(
            on_next=lambda info: self.dispatch(Action.get_storage_info_success(info)),
            on_error=lambda e: print(f"[Storage Info Error] {e}"),
        )
        self._disposables.add(after_file_gateway_connect)

        # Load projects effect
        load_projects_effect = self._actions_subject.pipe(
            ops.filter(lambda a: a.type == ActionType.LOAD_PROJECTS_REQUEST),
            ops.flat_map(lambda _: self._engine.list_projects()),
        ).subscribe(
            on_next=lambda projects: self.dispatch(Action.load_projects_success(projects)),
            on_error=lambda e: self.dispatch(Action.load_projects_failure(str(e))),
        )
        self._disposables.add(load_projects_effect)

        # Create project effect (2 steps: init structure in FileGateway, then register in Engine)
        create_project_effect = self._actions_subject.pipe(
            ops.filter(lambda a: a.type == ActionType.CREATE_PROJECT_REQUEST),
            ops.flat_map(
                lambda a: self._file_gateway.init_project_structure(a.payload["path"], a.payload["name"]).pipe(
                    ops.flat_map(
                        lambda result: self._engine.register_project(
                            a.payload["name"],
                            result["project_path"],
                            self._file_gateway.storage_id or "",
                        )
                    )
                )
            ),
        ).subscribe(
            on_next=lambda project: self.dispatch(Action.create_project_success(project)),
            on_error=lambda e: self.dispatch(Action.create_project_failure(str(e))),
        )
        self._disposables.add(create_project_effect)

        # Open project effect
        open_project_effect = self._actions_subject.pipe(
            ops.filter(lambda a: a.type == ActionType.OPEN_PROJECT_REQUEST),
            ops.flat_map(lambda a: self._engine.open_project(a.payload)),
        ).subscribe(
            on_next=lambda project: self.dispatch(Action.open_project_success(project)),
            on_error=lambda e: self.dispatch(Action.open_project_failure(str(e))),
        )
        self._disposables.add(open_project_effect)

        # Delete project effect
        delete_project_effect = self._actions_subject.pipe(
            ops.filter(lambda a: a.type == ActionType.DELETE_PROJECT_REQUEST),
            ops.flat_map(
                lambda a: self._engine.unregister_project(a.payload).pipe(
                    ops.map(lambda _: a.payload)
                )
            ),
        ).subscribe(
            on_next=lambda project_id: self.dispatch(Action.delete_project_success(project_id)),
            on_error=lambda e: self.dispatch(Action.delete_project_failure(str(e))),
        )
        self._disposables.add(delete_project_effect)
