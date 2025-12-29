"""gRPC клиент для DirectorEngine - сервиса обработки видео."""

from typing import Optional

import grpc
from reactivex import Observable
from reactivex import create

from app.models.project import EngineInfo, Project
from app.api.proto import director_pb2, director_pb2_grpc


class EngineClient:
    """Реактивный gRPC клиент для DirectorEngine."""

    def __init__(self, host: str = "localhost", port: int = 50051):
        self.address = f"{host}:{port}"
        self._channel: Optional[grpc.Channel] = None
        self._stub: Optional[director_pb2_grpc.ProjectServiceStub] = None

    @property
    def is_connected(self) -> bool:
        """Проверить подключение."""
        return self._channel is not None and self._stub is not None

    def connect(self) -> Observable[bool]:
        """Подключиться к серверу."""

        def subscribe(observer, scheduler):
            try:
                self._channel = grpc.insecure_channel(self.address)
                self._stub = director_pb2_grpc.ProjectServiceStub(self._channel)
                grpc.channel_ready_future(self._channel).result(timeout=5)
                observer.on_next(True)
                observer.on_completed()
            except grpc.FutureTimeoutError:
                self._channel = None
                self._stub = None
                observer.on_next(False)
                observer.on_completed()
            except Exception as e:
                observer.on_error(e)

        return create(subscribe)

    def disconnect(self) -> None:
        """Отключиться от сервера."""
        if self._channel:
            self._channel.close()
            self._channel = None
            self._stub = None

    def get_engine_info(self) -> Observable[EngineInfo]:
        """Получить информацию о движке."""

        def subscribe(observer, scheduler):
            if not self._stub:
                observer.on_error(ConnectionError("Не подключено к DirectorEngine"))
                return

            try:
                request = director_pb2.GetEngineInfoRequest()
                response = self._stub.GetEngineInfo(request)
                info = EngineInfo.from_proto(response)
                observer.on_next(info)
                observer.on_completed()
            except Exception as e:
                observer.on_error(e)

        return create(subscribe)

    def list_projects(self) -> Observable[list[Project]]:
        """Получить список проектов."""

        def subscribe(observer, scheduler):
            if not self._stub:
                observer.on_error(ConnectionError("Не подключено к DirectorEngine"))
                return

            try:
                request = director_pb2.ListProjectsRequest()
                response = self._stub.ListProjects(request)
                projects = [Project.from_proto(p) for p in response.projects]
                observer.on_next(projects)
                observer.on_completed()
            except Exception as e:
                observer.on_error(e)

        return create(subscribe)

    def register_project(
        self, name: str, path: str, file_gateway_id: str
    ) -> Observable[Project]:
        """Зарегистрировать проект в движке."""

        def subscribe(observer, scheduler):
            if not self._stub:
                observer.on_error(ConnectionError("Не подключено к DirectorEngine"))
                return

            try:
                request = director_pb2.RegisterProjectRequest(
                    name=name,
                    path=path,
                    file_gateway_id=file_gateway_id,
                )
                response = self._stub.RegisterProject(request)

                if response.success and response.project.id:
                    project = Project.from_proto(response.project)
                    observer.on_next(project)
                    observer.on_completed()
                else:
                    observer.on_error(Exception(response.error_message or "Ошибка регистрации проекта"))
            except Exception as e:
                observer.on_error(e)

        return create(subscribe)

    def open_project(self, project_id: str) -> Observable[Project]:
        """Открыть проект."""

        def subscribe(observer, scheduler):
            if not self._stub:
                observer.on_error(ConnectionError("Не подключено к DirectorEngine"))
                return

            try:
                request = director_pb2.OpenProjectRequest(project_id=project_id)
                response = self._stub.OpenProject(request)

                if response.success and response.project.id:
                    project = Project.from_proto(response.project)
                    observer.on_next(project)
                    observer.on_completed()
                else:
                    observer.on_error(Exception(response.error_message or "Ошибка открытия проекта"))
            except Exception as e:
                observer.on_error(e)

        return create(subscribe)

    def unregister_project(self, project_id: str) -> Observable[bool]:
        """Удалить проект из реестра."""

        def subscribe(observer, scheduler):
            if not self._stub:
                observer.on_error(ConnectionError("Не подключено к DirectorEngine"))
                return

            try:
                request = director_pb2.UnregisterProjectRequest(project_id=project_id)
                response = self._stub.UnregisterProject(request)

                if response.success:
                    observer.on_next(True)
                    observer.on_completed()
                else:
                    observer.on_error(Exception(response.error_message or "Ошибка удаления проекта"))
            except Exception as e:
                observer.on_error(e)

        return create(subscribe)

