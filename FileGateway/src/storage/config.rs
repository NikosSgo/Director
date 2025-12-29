//! Конфигурация хранилища

use serde::{Deserialize, Serialize};
use std::path::PathBuf;

/// Тип хранилища
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "lowercase")]
pub enum StorageType {
    #[default]
    Local,
    S3,
}

/// Конфигурация хранилища
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StorageConfig {
    /// Тип хранилища
    #[serde(default)]
    pub storage_type: StorageType,

    /// Уникальный ID хранилища (генерируется автоматически если не задан)
    pub id: Option<String>,

    /// Путь по умолчанию для проектов
    pub default_projects_path: Option<String>,

    // === Настройки для Local ===
    
    /// Показывать скрытые файлы
    #[serde(default)]
    pub show_hidden: bool,

    // === Настройки для S3 (будущее) ===
    
    /// Endpoint S3 (например, http://localhost:9000 для MinIO)
    pub s3_endpoint: Option<String>,
    
    /// Регион
    pub s3_region: Option<String>,
    
    /// Access Key
    pub s3_access_key: Option<String>,
    
    /// Secret Key
    pub s3_secret_key: Option<String>,
    
    /// Имя бакета по умолчанию
    pub s3_bucket: Option<String>,
}

impl Default for StorageConfig {
    fn default() -> Self {
        Self {
            storage_type: StorageType::Local,
            id: None,
            default_projects_path: None,
            show_hidden: false,
            s3_endpoint: None,
            s3_region: None,
            s3_access_key: None,
            s3_secret_key: None,
            s3_bucket: None,
        }
    }
}

impl StorageConfig {
    /// Загрузить конфигурацию из файла
    pub fn load(path: &PathBuf) -> Result<Self, Box<dyn std::error::Error>> {
        let content = std::fs::read_to_string(path)?;
        let config: StorageConfig = serde_json::from_str(&content)?;
        Ok(config)
    }

    /// Сохранить конфигурацию в файл
    pub fn save(&self, path: &PathBuf) -> Result<(), Box<dyn std::error::Error>> {
        let content = serde_json::to_string_pretty(self)?;
        std::fs::write(path, content)?;
        Ok(())
    }

    /// Создать конфигурацию для локального хранилища
    pub fn local() -> Self {
        Self {
            storage_type: StorageType::Local,
            ..Default::default()
        }
    }

    /// Создать конфигурацию для MinIO
    pub fn minio(endpoint: &str, access_key: &str, secret_key: &str, bucket: &str) -> Self {
        Self {
            storage_type: StorageType::S3,
            s3_endpoint: Some(endpoint.to_string()),
            s3_region: Some("us-east-1".to_string()),
            s3_access_key: Some(access_key.to_string()),
            s3_secret_key: Some(secret_key.to_string()),
            s3_bucket: Some(bucket.to_string()),
            ..Default::default()
        }
    }
}

