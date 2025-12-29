//! Типы данных для работы с хранилищем

use serde::{Deserialize, Serialize};

/// Информация о хранилище
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StorageInfo {
    /// Уникальный идентификатор хранилища
    pub id: String,
    /// Тип хранилища (local, s3, etc.)
    pub storage_type: String,
    /// Имя хоста
    pub hostname: String,
    /// Операционная система
    pub os: String,
    /// Домашняя директория (для локального)
    pub home_directory: String,
    /// Путь по умолчанию для проектов
    pub default_projects_path: String,
    /// Корневые пути (диски, бакеты)
    pub root_paths: Vec<String>,
    /// Общий размер (байты)
    pub total_space: u64,
    /// Свободное место (байты)
    pub free_space: u64,
}

/// Элемент директории/бакета
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StorageEntry {
    /// Имя файла/директории
    pub name: String,
    /// Полный путь/ключ
    pub path: String,
    /// Это директория?
    pub is_directory: bool,
    /// Размер в байтах
    pub size: u64,
    /// Время создания (unix timestamp)
    pub created_at: i64,
    /// Время изменения (unix timestamp)
    pub modified_at: i64,
    /// MIME тип
    pub mime_type: String,
    /// Дополнительные метаданные
    pub metadata: std::collections::HashMap<String, String>,
}

/// Содержимое директории
#[derive(Debug, Clone)]
pub struct DirectoryListing {
    /// Текущий путь
    pub current_path: String,
    /// Родительский путь (пустой если корень)
    pub parent_path: String,
    /// Содержимое
    pub entries: Vec<StorageEntry>,
}

/// Результат загрузки файла
#[derive(Debug, Clone)]
pub struct UploadResult {
    /// Путь к загруженному файлу
    pub path: String,
    /// Размер в байтах
    pub size: u64,
    /// Контрольная сумма (опционально)
    pub checksum: Option<String>,
}

/// Структура проекта
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectStructure {
    /// Корневой путь проекта
    pub project_path: String,
    /// Путь к ассетам
    pub assets_path: String,
    /// Путь к видео
    pub video_path: String,
    /// Путь к аудио
    pub audio_path: String,
    /// Путь к изображениям
    pub images_path: String,
    /// Путь к таймлайну
    pub timeline_path: String,
    /// Путь к экспортам
    pub exports_path: String,
}

