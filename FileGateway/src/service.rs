//! Реализация gRPC сервиса FileGateway

use std::pin::Pin;
use std::sync::Arc;

use tokio::io::AsyncReadExt;
use tokio_stream::{Stream, StreamExt};
use tonic::{Request, Response, Status, Streaming};
use tracing::{error, info};

use crate::proto::*;
use crate::storage::{StorageProvider, StorageConfig, create_provider};

pub struct FileGatewayImpl {
    provider: Arc<dyn StorageProvider>,
}

impl FileGatewayImpl {
    pub fn new() -> Result<Self, Box<dyn std::error::Error>> {
        // Загружаем конфигурацию или используем дефолтную
        let config = StorageConfig::local();
        let provider = create_provider(&config)?;
        
        Ok(Self { provider })
    }

    pub fn with_config(config: StorageConfig) -> Result<Self, Box<dyn std::error::Error>> {
        let provider = create_provider(&config)?;
        Ok(Self { provider })
    }
}

// Конвертация типов
impl From<crate::storage::StorageEntry> for DirectoryEntry {
    fn from(entry: crate::storage::StorageEntry) -> Self {
        DirectoryEntry {
            name: entry.name,
            path: entry.path,
            is_directory: entry.is_directory,
            size: entry.size,
            created_at: entry.created_at,
            modified_at: entry.modified_at,
            mime_type: entry.mime_type,
        }
    }
}

#[tonic::async_trait]
impl file_gateway_server::FileGateway for FileGatewayImpl {
    // === Информация о хранилище ===

    async fn get_storage_info(
        &self,
        _request: Request<GetStorageInfoRequest>,
    ) -> Result<Response<GetStorageInfoResponse>, Status> {
        info!("Запрос информации о хранилище");

        let info = self.provider.get_info().await.map_err(|e| {
            error!("Ошибка получения информации: {}", e);
            Status::internal(e.to_string())
        })?;

        Ok(Response::new(GetStorageInfoResponse {
            storage_id: info.id,
            hostname: info.hostname,
            os: info.os,
            home_directory: info.home_directory,
            default_projects_path: info.default_projects_path,
            root_paths: info.root_paths,
            total_space: info.total_space,
            free_space: info.free_space,
        }))
    }

    // === Навигация ===

    async fn browse_directory(
        &self,
        request: Request<BrowseDirectoryRequest>,
    ) -> Result<Response<BrowseDirectoryResponse>, Status> {
        let req = request.into_inner();
        info!("Просмотр директории: {}", if req.path.is_empty() { "~" } else { &req.path });

        match self.provider.list_directory(&req.path).await {
            Ok(listing) => {
                let entries: Vec<DirectoryEntry> = listing
                    .entries
                    .into_iter()
                    .map(DirectoryEntry::from)
                    .collect();

                Ok(Response::new(BrowseDirectoryResponse {
                    success: true,
                    error_message: String::new(),
                    current_path: listing.current_path,
                    parent_path: listing.parent_path,
                    entries,
                }))
            }
            Err(e) => {
                error!("Ошибка чтения директории: {}", e);
                Ok(Response::new(BrowseDirectoryResponse {
                    success: false,
                    error_message: e.to_string(),
                    ..Default::default()
                }))
            }
        }
    }

    async fn create_directory(
        &self,
        request: Request<CreateDirectoryRequest>,
    ) -> Result<Response<CreateDirectoryResponse>, Status> {
        let req = request.into_inner();
        info!("Создание директории: {}", req.path);

        match self.provider.create_directory(&req.path, req.create_parents).await {
            Ok(created_path) => Ok(Response::new(CreateDirectoryResponse {
                success: true,
                error_message: String::new(),
                created_path,
            })),
            Err(e) => {
                error!("Ошибка создания директории: {}", e);
                Ok(Response::new(CreateDirectoryResponse {
                    success: false,
                    error_message: e.to_string(),
                    created_path: String::new(),
                }))
            }
        }
    }

    async fn delete(
        &self,
        request: Request<DeleteRequest>,
    ) -> Result<Response<DeleteResponse>, Status> {
        let req = request.into_inner();
        info!("Удаление: {}, рекурсивно: {}", req.path, req.recursive);

        // Проверяем, файл это или директория
        let entry_info = self.provider.get_entry_info(&req.path).await;

        let result = match entry_info {
            Ok(entry) if entry.is_directory => {
                self.provider.delete_directory(&req.path, req.recursive).await
            }
            Ok(_) => {
                self.provider.delete_file(&req.path).await
            }
            Err(e) => Err(e),
        };

        match result {
            Ok(()) => Ok(Response::new(DeleteResponse {
                success: true,
                error_message: String::new(),
            })),
            Err(e) => {
                error!("Ошибка удаления: {}", e);
                Ok(Response::new(DeleteResponse {
                    success: false,
                    error_message: e.to_string(),
                }))
            }
        }
    }

    // === Загрузка файлов ===

    async fn upload_file(
        &self,
        request: Request<Streaming<UploadFileRequest>>,
    ) -> Result<Response<UploadFileResponse>, Status> {
        let mut stream = request.into_inner();

        // Первое сообщение - метаданные
        let first_message = stream
            .next()
            .await
            .ok_or_else(|| Status::invalid_argument("Пустой стрим"))??;

        let metadata = match first_message.data {
            Some(upload_file_request::Data::Metadata(m)) => m,
            _ => return Err(Status::invalid_argument("Первое сообщение должно содержать метаданные")),
        };

        info!(
            "Загрузка файла: {} в {}, размер: {} байт",
            metadata.filename, metadata.destination_path, metadata.total_size
        );

        let destination = format!("{}/{}", metadata.destination_path, metadata.filename);

        // Получаем поток для записи
        let mut write_stream = self.provider
            .get_write_stream(&destination, metadata.overwrite)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;

        let mut bytes_written: u64 = 0;

        // Записываем чанки
        while let Some(message) = stream.next().await {
            let message = message?;
            if let Some(upload_file_request::Data::Chunk(chunk)) = message.data {
                use tokio::io::AsyncWriteExt;
                write_stream.write_all(&chunk).await.map_err(|e| Status::internal(e.to_string()))?;
                bytes_written += chunk.len() as u64;
            }
        }

        use tokio::io::AsyncWriteExt;
        write_stream.flush().await.map_err(|e| Status::internal(e.to_string()))?;

        info!("Файл загружен: {}, {} байт", destination, bytes_written);

        Ok(Response::new(UploadFileResponse {
            success: true,
            error_message: String::new(),
            file_path: destination,
            bytes_written,
        }))
    }

    // === Скачивание файлов ===

    type DownloadFileStream = Pin<Box<dyn Stream<Item = Result<DownloadFileResponse, Status>> + Send>>;

    async fn download_file(
        &self,
        request: Request<DownloadFileRequest>,
    ) -> Result<Response<Self::DownloadFileStream>, Status> {
        let req = request.into_inner();
        info!("Скачивание файла: {}", req.path);

        // Получаем информацию о файле
        let entry = self.provider
            .get_entry_info(&req.path)
            .await
            .map_err(|e| Status::not_found(e.to_string()))?;

        if entry.is_directory {
            return Err(Status::invalid_argument("Путь является директорией"));
        }

        let filename = entry.name.clone();
        let mime_type = entry.mime_type.clone();
        let total_size = entry.size;

        // Получаем поток чтения
        let mut read_stream = self.provider
            .get_read_stream(&req.path)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;

        let stream = async_stream::try_stream! {
            // Отправляем метаданные
            yield DownloadFileResponse {
                data: Some(download_file_response::Data::Metadata(DownloadFileMetadata {
                    filename,
                    total_size,
                    mime_type,
                })),
            };

            // Отправляем данные чанками
            let mut buffer = vec![0u8; 64 * 1024]; // 64KB
            loop {
                let n = read_stream.read(&mut buffer).await?;
                if n == 0 {
                    break;
                }
                yield DownloadFileResponse {
                    data: Some(download_file_response::Data::Chunk(buffer[..n].to_vec())),
                };
            }
        };

        Ok(Response::new(Box::pin(stream)))
    }

    async fn get_file_info(
        &self,
        request: Request<GetFileInfoRequest>,
    ) -> Result<Response<GetFileInfoResponse>, Status> {
        let req = request.into_inner();

        match self.provider.get_entry_info(&req.path).await {
            Ok(entry) => Ok(Response::new(GetFileInfoResponse {
                success: true,
                error_message: String::new(),
                file_info: Some(DirectoryEntry::from(entry)),
            })),
            Err(e) => Ok(Response::new(GetFileInfoResponse {
                success: false,
                error_message: e.to_string(),
                file_info: None,
            })),
        }
    }

    // === Проекты ===

    async fn init_project_structure(
        &self,
        request: Request<InitProjectStructureRequest>,
    ) -> Result<Response<InitProjectStructureResponse>, Status> {
        let req = request.into_inner();
        info!("Инициализация проекта: {} в {}", req.project_name, req.base_path);

        match self.provider.init_project_structure(&req.base_path, &req.project_name).await {
            Ok(structure) => Ok(Response::new(InitProjectStructureResponse {
                success: true,
                error_message: String::new(),
                project_path: structure.project_path,
                assets_path: structure.assets_path,
                video_path: structure.video_path,
                audio_path: structure.audio_path,
                images_path: structure.images_path,
                timeline_path: structure.timeline_path,
                exports_path: structure.exports_path,
            })),
            Err(e) => {
                error!("Ошибка создания проекта: {}", e);
                Ok(Response::new(InitProjectStructureResponse {
                    success: false,
                    error_message: e.to_string(),
                    ..Default::default()
                }))
            }
        }
    }
}
