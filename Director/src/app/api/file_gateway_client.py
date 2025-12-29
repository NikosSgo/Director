"""gRPC клиент для FileGateway - сервиса работы с файлами."""

from typing import Optional

import grpc
from reactivex import Observable
from reactivex import create

from app.models.project import DirectoryListing, StorageInfo
from app.api.proto import file_gateway_pb2, file_gateway_pb2_grpc


class FileGatewayClient:
    """Реактивный gRPC клиент для FileGateway."""

    def __init__(self, host: str = "localhost", port: int = 50052):
        self.address = f"{host}:{port}"
        self._channel: Optional[grpc.Channel] = None
        self._stub: Optional[file_gateway_pb2_grpc.FileGatewayStub] = None
        self._storage_id: Optional[str] = None

    @property
    def is_connected(self) -> bool:
        """Проверить подключение."""
        return self._channel is not None and self._stub is not None

    @property
    def storage_id(self) -> Optional[str]:
        """ID подключённого хранилища."""
        return self._storage_id

    def connect(self) -> Observable[bool]:
        """Подключиться к серверу."""

        def subscribe(observer, scheduler):
            try:
                self._channel = grpc.insecure_channel(self.address)
                self._stub = file_gateway_pb2_grpc.FileGatewayStub(self._channel)
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
            self._storage_id = None

    def get_storage_info(self) -> Observable[StorageInfo]:
        """Получить информацию о хранилище."""

        def subscribe(observer, scheduler):
            if not self._stub:
                observer.on_error(ConnectionError("Не подключено к FileGateway"))
                return

            try:
                request = file_gateway_pb2.GetStorageInfoRequest()
                response = self._stub.GetStorageInfo(request)
                self._storage_id = response.storage_id
                info = StorageInfo.from_proto(response)
                observer.on_next(info)
                observer.on_completed()
            except Exception as e:
                observer.on_error(e)

        return create(subscribe)

    def browse_directory(self, path: str = "") -> Observable[DirectoryListing]:
        """Получить содержимое директории."""

        def subscribe(observer, scheduler):
            if not self._stub:
                observer.on_error(ConnectionError("Не подключено к FileGateway"))
                return

            try:
                request = file_gateway_pb2.BrowseDirectoryRequest(path=path)
                response = self._stub.BrowseDirectory(request)

                if response.success:
                    listing = DirectoryListing.from_file_gateway_proto(response)
                    observer.on_next(listing)
                    observer.on_completed()
                else:
                    observer.on_error(Exception(response.error_message or "Ошибка чтения директории"))
            except Exception as e:
                observer.on_error(e)

        return create(subscribe)

    def create_directory(self, path: str, create_parents: bool = True) -> Observable[str]:
        """Создать директорию. Возвращает путь к созданной директории."""

        def subscribe(observer, scheduler):
            if not self._stub:
                observer.on_error(ConnectionError("Не подключено к FileGateway"))
                return

            try:
                request = file_gateway_pb2.CreateDirectoryRequest(
                    path=path,
                    create_parents=create_parents,
                )
                response = self._stub.CreateDirectory(request)

                if response.success:
                    observer.on_next(response.created_path)
                    observer.on_completed()
                else:
                    observer.on_error(Exception(response.error_message or "Ошибка создания директории"))
            except Exception as e:
                observer.on_error(e)

        return create(subscribe)

    def init_project_structure(self, base_path: str, project_name: str) -> Observable[dict]:
        """
        Создать структуру проекта.
        Возвращает словарь с путями к директориям проекта.
        """

        def subscribe(observer, scheduler):
            if not self._stub:
                observer.on_error(ConnectionError("Не подключено к FileGateway"))
                return

            try:
                request = file_gateway_pb2.InitProjectStructureRequest(
                    base_path=base_path,
                    project_name=project_name,
                )
                response = self._stub.InitProjectStructure(request)

                if response.success:
                    result = {
                        "project_path": response.project_path,
                        "assets_path": response.assets_path,
                        "video_path": response.video_path,
                        "audio_path": response.audio_path,
                        "images_path": response.images_path,
                        "timeline_path": response.timeline_path,
                        "exports_path": response.exports_path,
                    }
                    observer.on_next(result)
                    observer.on_completed()
                else:
                    observer.on_error(Exception(response.error_message or "Ошибка создания проекта"))
            except Exception as e:
                observer.on_error(e)

        return create(subscribe)

    def delete(self, path: str, recursive: bool = False) -> Observable[bool]:
        """Удалить файл или директорию."""

        def subscribe(observer, scheduler):
            if not self._stub:
                observer.on_error(ConnectionError("Не подключено к FileGateway"))
                return

            try:
                request = file_gateway_pb2.DeleteRequest(path=path, recursive=recursive)
                response = self._stub.Delete(request)

                if response.success:
                    observer.on_next(True)
                    observer.on_completed()
                else:
                    observer.on_error(Exception(response.error_message or "Ошибка удаления"))
            except Exception as e:
                observer.on_error(e)

        return create(subscribe)

