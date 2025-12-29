"""Клиент для API Gateway - единая точка входа для всех сервисов."""

from typing import Optional, Callable
import grpc

from app.api.proto import api_gateway_pb2, api_gateway_pb2_grpc


class GatewayClient:
    """Клиент для API Gateway."""

    def __init__(self, address: str = "[::1]:50050"):
        self._address = address
        self._channel: Optional[grpc.Channel] = None
        self._stub: Optional[api_gateway_pb2_grpc.ApiGatewayStub] = None

    def connect(self) -> bool:
        """Подключиться к API Gateway."""
        try:
            self._channel = grpc.insecure_channel(self._address)
            self._stub = api_gateway_pb2_grpc.ApiGatewayStub(self._channel)
            # Проверяем подключение
            self.health_check()
            return True
        except grpc.RpcError:
            return False

    def disconnect(self) -> None:
        """Отключиться от сервера."""
        if self._channel:
            self._channel.close()
            self._channel = None
            self._stub = None

    @property
    def is_connected(self) -> bool:
        return self._stub is not None

    # === Health Check ===

    def health_check(self) -> api_gateway_pb2.HealthCheckResponse:
        """Проверить состояние всех сервисов."""
        return self._stub.HealthCheck(api_gateway_pb2.HealthCheckRequest())

    def get_services_info(self) -> api_gateway_pb2.GetServicesInfoResponse:
        """Получить информацию о всех сервисах."""
        return self._stub.GetServicesInfo(api_gateway_pb2.GetServicesInfoRequest())

    # === Проекты ===

    def list_projects(self) -> api_gateway_pb2.ListProjectsResponse:
        """Получить список проектов."""
        return self._stub.ListProjects(api_gateway_pb2.ListProjectsRequest())

    def create_project(self, name: str, path: str) -> api_gateway_pb2.CreateProjectResponse:
        """Создать новый проект."""
        return self._stub.CreateProject(
            api_gateway_pb2.CreateProjectRequest(name=name, path=path)
        )

    def open_project(self, project_id: str) -> api_gateway_pb2.OpenProjectResponse:
        """Открыть проект."""
        return self._stub.OpenProject(
            api_gateway_pb2.OpenProjectRequest(project_id=project_id)
        )

    def delete_project(
        self, project_id: str, delete_files: bool = False
    ) -> api_gateway_pb2.DeleteProjectResponse:
        """Удалить проект."""
        return self._stub.DeleteProject(
            api_gateway_pb2.DeleteProjectRequest(
                project_id=project_id, delete_files=delete_files
            )
        )

    # === Файловая система ===

    def get_storage_info(self) -> api_gateway_pb2.GetStorageInfoResponse:
        """Получить информацию о хранилище."""
        return self._stub.GetStorageInfo(api_gateway_pb2.GetStorageInfoRequest())

    def browse_directory(self, path: str = "") -> api_gateway_pb2.BrowseDirectoryResponse:
        """Просмотреть директорию."""
        return self._stub.BrowseDirectory(
            api_gateway_pb2.BrowseDirectoryRequest(path=path)
        )

    def create_directory(
        self, path: str, create_parents: bool = True
    ) -> api_gateway_pb2.CreateDirectoryResponse:
        """Создать директорию."""
        return self._stub.CreateDirectory(
            api_gateway_pb2.CreateDirectoryRequest(
                path=path, create_parents=create_parents
            )
        )

    def delete(
        self, path: str, recursive: bool = False
    ) -> api_gateway_pb2.DeleteResponse:
        """Удалить файл или директорию."""
        return self._stub.Delete(
            api_gateway_pb2.DeleteRequest(path=path, recursive=recursive)
        )

    def init_project_structure(
        self, base_path: str, project_name: str
    ) -> api_gateway_pb2.InitProjectStructureResponse:
        """Создать структуру проекта."""
        return self._stub.InitProjectStructure(
            api_gateway_pb2.InitProjectStructureRequest(
                base_path=base_path, project_name=project_name
            )
        )

    # === Загрузка файлов ===

    def upload_file(
        self,
        local_path: str,
        destination_path: str,
        filename: str,
        overwrite: bool = False,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> api_gateway_pb2.UploadFileResponse:
        """
        Загрузить файл на сервер.
        
        Args:
            local_path: Локальный путь к файлу
            destination_path: Путь на сервере
            filename: Имя файла
            overwrite: Перезаписать если существует
            progress_callback: Callback(bytes_sent, total_bytes)
        """
        import os

        file_size = os.path.getsize(local_path)

        def generate_chunks():
            # Сначала отправляем метаданные
            yield api_gateway_pb2.UploadFileRequest(
                metadata=api_gateway_pb2.UploadFileMetadata(
                    destination_path=destination_path,
                    filename=filename,
                    total_size=file_size,
                    overwrite=overwrite,
                )
            )

            # Потом чанки данных
            bytes_sent = 0
            chunk_size = 64 * 1024  # 64KB

            with open(local_path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    bytes_sent += len(chunk)
                    if progress_callback:
                        progress_callback(bytes_sent, file_size)
                    yield api_gateway_pb2.UploadFileRequest(chunk=chunk)

        return self._stub.UploadFile(generate_chunks())

    def download_file(
        self,
        remote_path: str,
        local_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        """
        Скачать файл с сервера.
        
        Args:
            remote_path: Путь к файлу на сервере
            local_path: Локальный путь для сохранения
            progress_callback: Callback(bytes_received, total_bytes)
        
        Returns:
            True если успешно
        """
        response_stream = self._stub.DownloadFile(
            api_gateway_pb2.DownloadFileRequest(path=remote_path)
        )

        total_size = 0
        bytes_received = 0

        with open(local_path, "wb") as f:
            for response in response_stream:
                if response.HasField("metadata"):
                    total_size = response.metadata.total_size
                elif response.HasField("chunk"):
                    f.write(response.chunk)
                    bytes_received += len(response.chunk)
                    if progress_callback and total_size > 0:
                        progress_callback(bytes_received, total_size)

        return True

