//! Модуль абстракции хранилища
//!
//! Поддерживаемые провайдеры:
//! - `LocalStorageProvider` - локальная файловая система
//! - `S3StorageProvider` - S3-совместимые хранилища (MinIO, AWS S3, etc.) [будущее]

mod provider;
mod local;
mod config;
mod types;

pub use provider::StorageProvider;
pub use local::LocalStorageProvider;
pub use config::{StorageConfig, StorageType};
pub use types::*;

use std::sync::Arc;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum StorageError {
    #[error("Путь не существует: {0}")]
    NotFound(String),

    #[error("Путь не является директорией: {0}")]
    NotADirectory(String),

    #[error("Путь не является файлом: {0}")]
    NotAFile(String),

    #[error("Файл уже существует: {0}")]
    AlreadyExists(String),

    #[error("Недостаточно прав: {0}")]
    PermissionDenied(String),

    #[error("Ошибка ввода-вывода: {0}")]
    Io(#[from] std::io::Error),

    #[error("Ошибка конфигурации: {0}")]
    Config(String),

    #[error("Провайдер не поддерживает эту операцию")]
    NotSupported,
}

/// Создать провайдер хранилища из конфигурации
pub fn create_provider(config: &StorageConfig) -> Result<Arc<dyn StorageProvider>, StorageError> {
    match config.storage_type {
        StorageType::Local => {
            let provider = LocalStorageProvider::new(config)?;
            Ok(Arc::new(provider))
        }
        StorageType::S3 => {
            // TODO: Реализовать S3 провайдер
            Err(StorageError::NotSupported)
        }
    }
}

