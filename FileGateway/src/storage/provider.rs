//! Trait абстракции хранилища

use async_trait::async_trait;
use bytes::Bytes;
use tokio::io::{AsyncRead, AsyncWrite};
use std::pin::Pin;

use super::{StorageError, StorageInfo, StorageEntry, DirectoryListing, UploadResult, ProjectStructure};

/// Абстракция провайдера хранилища
/// 
/// Реализуйте этот trait для поддержки нового типа хранилища.
/// 
/// # Пример
/// 
/// ```rust,ignore
/// struct MyStorageProvider { ... }
/// 
/// #[async_trait]
/// impl StorageProvider for MyStorageProvider {
///     async fn get_info(&self) -> Result<StorageInfo, StorageError> { ... }
///     // ...
/// }
/// ```
#[async_trait]
pub trait StorageProvider: Send + Sync {
    // === Информация ===

    /// Получить информацию о хранилище
    async fn get_info(&self) -> Result<StorageInfo, StorageError>;

    // === Навигация ===

    /// Получить содержимое директории/бакета
    /// 
    /// * `path` - путь к директории (пустая строка = корень/домашняя)
    async fn list_directory(&self, path: &str) -> Result<DirectoryListing, StorageError>;

    /// Проверить существование пути
    async fn exists(&self, path: &str) -> Result<bool, StorageError>;

    /// Получить информацию о файле/директории
    async fn get_entry_info(&self, path: &str) -> Result<StorageEntry, StorageError>;

    // === Операции с директориями ===

    /// Создать директорию
    /// 
    /// * `path` - путь к директории
    /// * `recursive` - создавать родительские директории
    async fn create_directory(&self, path: &str, recursive: bool) -> Result<String, StorageError>;

    /// Удалить директорию
    /// 
    /// * `path` - путь к директории
    /// * `recursive` - удалять содержимое
    async fn delete_directory(&self, path: &str, recursive: bool) -> Result<(), StorageError>;

    // === Операции с файлами ===

    /// Удалить файл
    async fn delete_file(&self, path: &str) -> Result<(), StorageError>;

    /// Загрузить файл (для небольших файлов)
    /// 
    /// * `destination` - путь назначения
    /// * `data` - данные файла
    /// * `overwrite` - перезаписать если существует
    async fn upload_bytes(
        &self,
        destination: &str,
        data: Bytes,
        overwrite: bool,
    ) -> Result<UploadResult, StorageError>;

    /// Скачать файл (для небольших файлов)
    async fn download_bytes(&self, path: &str) -> Result<Bytes, StorageError>;

    /// Получить поток для чтения файла (для больших файлов)
    async fn get_read_stream(
        &self,
        path: &str,
    ) -> Result<Pin<Box<dyn AsyncRead + Send>>, StorageError>;

    /// Получить поток для записи файла (для больших файлов)
    async fn get_write_stream(
        &self,
        path: &str,
        overwrite: bool,
    ) -> Result<Pin<Box<dyn AsyncWrite + Send>>, StorageError>;

    // === Проекты ===

    /// Создать структуру проекта
    /// 
    /// * `base_path` - базовая директория
    /// * `project_name` - название проекта
    async fn init_project_structure(
        &self,
        base_path: &str,
        project_name: &str,
    ) -> Result<ProjectStructure, StorageError>;

    // === Утилиты ===

    /// Копировать файл
    async fn copy(&self, source: &str, destination: &str) -> Result<(), StorageError> {
        let data = self.download_bytes(source).await?;
        self.upload_bytes(destination, data, false).await?;
        Ok(())
    }

    /// Переместить файл
    async fn rename(&self, source: &str, destination: &str) -> Result<(), StorageError> {
        self.copy(source, destination).await?;
        self.delete_file(source).await?;
        Ok(())
    }
}

