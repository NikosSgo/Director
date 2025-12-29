//! Локальный провайдер хранилища (файловая система)

use async_trait::async_trait;
use bytes::Bytes;
use std::collections::HashMap;
use std::path::PathBuf;
use std::pin::Pin;
use tokio::fs;
use tokio::io::{AsyncRead, AsyncWrite};
use uuid::Uuid;

use super::{
    config::StorageConfig,
    provider::StorageProvider,
    types::*,
    StorageError,
};

/// Провайдер для локальной файловой системы
pub struct LocalStorageProvider {
    id: String,
    show_hidden: bool,
    default_projects_path: PathBuf,
}

impl LocalStorageProvider {
    pub fn new(config: &StorageConfig) -> Result<Self, StorageError> {
        let id = config.id.clone().unwrap_or_else(|| Uuid::new_v4().to_string());
        
        let default_projects_path = config
            .default_projects_path
            .as_ref()
            .map(PathBuf::from)
            .or_else(|| {
                directories::UserDirs::new()
                    .and_then(|d| d.video_dir().map(|p| p.to_path_buf()))
            })
            .unwrap_or_else(|| {
                directories::UserDirs::new()
                    .map(|d| d.home_dir().join("Videos"))
                    .unwrap_or_else(|| PathBuf::from("/tmp"))
            });

        Ok(Self {
            id,
            show_hidden: config.show_hidden,
            default_projects_path,
        })
    }

    fn get_home_directory(&self) -> PathBuf {
        directories::UserDirs::new()
            .map(|d| d.home_dir().to_path_buf())
            .unwrap_or_else(|| PathBuf::from("/"))
    }

    fn get_root_paths(&self) -> Vec<String> {
        #[cfg(target_os = "windows")]
        {
            (b'A'..=b'Z')
                .filter_map(|c| {
                    let drive = format!("{}:\\", c as char);
                    if std::path::Path::new(&drive).exists() {
                        Some(drive)
                    } else {
                        None
                    }
                })
                .collect()
        }

        #[cfg(not(target_os = "windows"))]
        {
            let mut paths = vec!["/".to_string()];
            
            if std::path::Path::new("/home").exists() {
                paths.push("/home".to_string());
            }
            
            for mount_point in &["/media", "/mnt", "/run/media"] {
                if let Ok(entries) = std::fs::read_dir(mount_point) {
                    for entry in entries.filter_map(|e| e.ok()) {
                        if entry.path().is_dir() {
                            paths.push(entry.path().to_string_lossy().to_string());
                        }
                    }
                }
            }
            
            paths
        }
    }

    fn get_disk_space(&self) -> (u64, u64) {
        #[cfg(target_os = "linux")]
        {
            use std::ffi::CString;
            use std::mem::MaybeUninit;
            
            let c_path = CString::new("/").unwrap();
            
            unsafe {
                let mut stat: MaybeUninit<libc::statvfs> = MaybeUninit::uninit();
                if libc::statvfs(c_path.as_ptr(), stat.as_mut_ptr()) == 0 {
                    let stat = stat.assume_init();
                    let total = stat.f_blocks as u64 * stat.f_frsize as u64;
                    let free = stat.f_bavail as u64 * stat.f_frsize as u64;
                    (total, free)
                } else {
                    (0, 0)
                }
            }
        }

        #[cfg(not(target_os = "linux"))]
        {
            (0, 0)
        }
    }

    fn resolve_path(&self, path: &str) -> PathBuf {
        if path.is_empty() {
            self.get_home_directory()
        } else {
            PathBuf::from(path)
        }
    }

    fn entry_from_metadata(
        &self,
        name: String,
        path: PathBuf,
        metadata: std::fs::Metadata,
    ) -> StorageEntry {
        let created_at = metadata
            .created()
            .ok()
            .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
            .map(|d| d.as_secs() as i64)
            .unwrap_or(0);

        let modified_at = metadata
            .modified()
            .ok()
            .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
            .map(|d| d.as_secs() as i64)
            .unwrap_or(0);

        let mime_type = if metadata.is_file() {
            mime_guess::from_path(&path)
                .first_or_octet_stream()
                .to_string()
        } else {
            "inode/directory".to_string()
        };

        StorageEntry {
            name,
            path: path.to_string_lossy().to_string(),
            is_directory: metadata.is_dir(),
            size: if metadata.is_file() { metadata.len() } else { 0 },
            created_at,
            modified_at,
            mime_type,
            metadata: HashMap::new(),
        }
    }
}

#[async_trait]
impl StorageProvider for LocalStorageProvider {
    async fn get_info(&self) -> Result<StorageInfo, StorageError> {
        let hostname = hostname::get()
            .map(|h| h.to_string_lossy().to_string())
            .unwrap_or_else(|_| "unknown".to_string());

        let (total_space, free_space) = self.get_disk_space();

        Ok(StorageInfo {
            id: self.id.clone(),
            storage_type: "local".to_string(),
            hostname,
            os: std::env::consts::OS.to_string(),
            home_directory: self.get_home_directory().to_string_lossy().to_string(),
            default_projects_path: self.default_projects_path.to_string_lossy().to_string(),
            root_paths: self.get_root_paths(),
            total_space,
            free_space,
        })
    }

    async fn list_directory(&self, path: &str) -> Result<DirectoryListing, StorageError> {
        let dir_path = self.resolve_path(path);

        if !dir_path.exists() {
            return Err(StorageError::NotFound(dir_path.to_string_lossy().to_string()));
        }

        if !dir_path.is_dir() {
            return Err(StorageError::NotADirectory(dir_path.to_string_lossy().to_string()));
        }

        let mut entries = Vec::new();
        let mut read_dir = fs::read_dir(&dir_path).await?;

        while let Some(entry) = read_dir.next_entry().await? {
            let name = entry.file_name().to_string_lossy().to_string();
            
            // Пропускаем скрытые файлы если не разрешено
            if !self.show_hidden && name.starts_with('.') {
                continue;
            }

            if let Ok(metadata) = entry.metadata().await {
                entries.push(self.entry_from_metadata(name, entry.path(), metadata));
            }
        }

        // Сортировка: директории сверху, потом по имени
        entries.sort_by(|a, b| {
            match (a.is_directory, b.is_directory) {
                (true, false) => std::cmp::Ordering::Less,
                (false, true) => std::cmp::Ordering::Greater,
                _ => a.name.to_lowercase().cmp(&b.name.to_lowercase()),
            }
        });

        let parent_path = dir_path
            .parent()
            .map(|p| p.to_string_lossy().to_string())
            .unwrap_or_default();

        Ok(DirectoryListing {
            current_path: dir_path.to_string_lossy().to_string(),
            parent_path,
            entries,
        })
    }

    async fn exists(&self, path: &str) -> Result<bool, StorageError> {
        let file_path = self.resolve_path(path);
        Ok(file_path.exists())
    }

    async fn get_entry_info(&self, path: &str) -> Result<StorageEntry, StorageError> {
        let file_path = self.resolve_path(path);
        
        if !file_path.exists() {
            return Err(StorageError::NotFound(path.to_string()));
        }

        let metadata = fs::metadata(&file_path).await?;
        let name = file_path
            .file_name()
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_default();

        Ok(self.entry_from_metadata(name, file_path, metadata.into()))
    }

    async fn create_directory(&self, path: &str, recursive: bool) -> Result<String, StorageError> {
        let dir_path = PathBuf::from(path);

        if recursive {
            fs::create_dir_all(&dir_path).await?;
        } else {
            fs::create_dir(&dir_path).await?;
        }

        Ok(dir_path.to_string_lossy().to_string())
    }

    async fn delete_directory(&self, path: &str, recursive: bool) -> Result<(), StorageError> {
        let dir_path = PathBuf::from(path);

        if !dir_path.exists() {
            return Err(StorageError::NotFound(path.to_string()));
        }

        if !dir_path.is_dir() {
            return Err(StorageError::NotADirectory(path.to_string()));
        }

        if recursive {
            fs::remove_dir_all(&dir_path).await?;
        } else {
            fs::remove_dir(&dir_path).await?;
        }

        Ok(())
    }

    async fn delete_file(&self, path: &str) -> Result<(), StorageError> {
        let file_path = PathBuf::from(path);

        if !file_path.exists() {
            return Err(StorageError::NotFound(path.to_string()));
        }

        if file_path.is_dir() {
            return Err(StorageError::NotAFile(path.to_string()));
        }

        fs::remove_file(&file_path).await?;
        Ok(())
    }

    async fn upload_bytes(
        &self,
        destination: &str,
        data: Bytes,
        overwrite: bool,
    ) -> Result<UploadResult, StorageError> {
        let file_path = PathBuf::from(destination);

        if file_path.exists() && !overwrite {
            return Err(StorageError::AlreadyExists(destination.to_string()));
        }

        // Создаём родительские директории
        if let Some(parent) = file_path.parent() {
            fs::create_dir_all(parent).await?;
        }

        let size = data.len() as u64;
        fs::write(&file_path, &data).await?;

        Ok(UploadResult {
            path: file_path.to_string_lossy().to_string(),
            size,
            checksum: None,
        })
    }

    async fn download_bytes(&self, path: &str) -> Result<Bytes, StorageError> {
        let file_path = PathBuf::from(path);

        if !file_path.exists() {
            return Err(StorageError::NotFound(path.to_string()));
        }

        if file_path.is_dir() {
            return Err(StorageError::NotAFile(path.to_string()));
        }

        let data = fs::read(&file_path).await?;
        Ok(Bytes::from(data))
    }

    async fn get_read_stream(
        &self,
        path: &str,
    ) -> Result<Pin<Box<dyn AsyncRead + Send>>, StorageError> {
        let file_path = PathBuf::from(path);

        if !file_path.exists() {
            return Err(StorageError::NotFound(path.to_string()));
        }

        let file = fs::File::open(&file_path).await?;
        Ok(Box::pin(file))
    }

    async fn get_write_stream(
        &self,
        path: &str,
        overwrite: bool,
    ) -> Result<Pin<Box<dyn AsyncWrite + Send>>, StorageError> {
        let file_path = PathBuf::from(path);

        if file_path.exists() && !overwrite {
            return Err(StorageError::AlreadyExists(path.to_string()));
        }

        // Создаём родительские директории
        if let Some(parent) = file_path.parent() {
            fs::create_dir_all(parent).await?;
        }

        let file = fs::File::create(&file_path).await?;
        Ok(Box::pin(file))
    }

    async fn init_project_structure(
        &self,
        base_path: &str,
        project_name: &str,
    ) -> Result<ProjectStructure, StorageError> {
        let project_path = PathBuf::from(base_path).join(project_name);

        if project_path.exists() {
            return Err(StorageError::AlreadyExists(
                project_path.to_string_lossy().to_string(),
            ));
        }

        let assets_path = project_path.join("assets");
        let video_path = assets_path.join("video");
        let audio_path = assets_path.join("audio");
        let images_path = assets_path.join("images");
        let timeline_path = project_path.join("timeline");
        let exports_path = project_path.join("exports");

        // Создаём все директории
        for dir in [
            &project_path,
            &assets_path,
            &video_path,
            &audio_path,
            &images_path,
            &timeline_path,
            &exports_path,
        ] {
            fs::create_dir_all(dir).await?;
        }

        Ok(ProjectStructure {
            project_path: project_path.to_string_lossy().to_string(),
            assets_path: assets_path.to_string_lossy().to_string(),
            video_path: video_path.to_string_lossy().to_string(),
            audio_path: audio_path.to_string_lossy().to_string(),
            images_path: images_path.to_string_lossy().to_string(),
            timeline_path: timeline_path.to_string_lossy().to_string(),
            exports_path: exports_path.to_string_lossy().to_string(),
        })
    }
}

