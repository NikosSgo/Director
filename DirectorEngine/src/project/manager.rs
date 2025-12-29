use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;
use thiserror::Error;
use uuid::Uuid;

#[derive(Error, Debug)]
pub enum ProjectError {
    #[error("Ошибка ввода-вывода: {0}")]
    IoError(#[from] std::io::Error),

    #[error("Проект уже зарегистрирован: {0}")]
    ProjectAlreadyExists(String),

    #[error("Проект не найден: {0}")]
    ProjectNotFound(String),

    #[error("Ошибка сериализации: {0}")]
    SerializationError(#[from] serde_json::Error),

    #[error("Не удалось определить директорию данных приложения")]
    DataDirNotFound,
}

/// Метаданные проекта
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectMetadata {
    pub id: String,
    pub name: String,
    pub path: String,
    pub file_gateway_id: String,
    pub created_at: DateTime<Utc>,
    pub modified_at: DateTime<Utc>,
}

/// Менеджер проектов - управляет реестром проектов
pub struct ProjectManager {
    projects: HashMap<String, ProjectMetadata>,
    projects_index_path: PathBuf,
}

impl ProjectManager {
    pub fn new() -> Result<Self, ProjectError> {
        let app_data_dir = directories::ProjectDirs::from("com", "director", "DirectorEngine")
            .ok_or(ProjectError::DataDirNotFound)?
            .data_dir()
            .to_path_buf();

        fs::create_dir_all(&app_data_dir)?;

        let projects_index_path = app_data_dir.join("projects.json");

        let mut manager = Self {
            projects: HashMap::new(),
            projects_index_path,
        };

        manager.load_projects_index()?;

        Ok(manager)
    }

    /// Загрузить индекс проектов из файла
    fn load_projects_index(&mut self) -> Result<(), ProjectError> {
        if self.projects_index_path.exists() {
            let content = fs::read_to_string(&self.projects_index_path)?;
            let projects: Vec<ProjectMetadata> = serde_json::from_str(&content)?;
            self.projects = projects.into_iter().map(|p| (p.id.clone(), p)).collect();
        }
        Ok(())
    }

    /// Сохранить индекс проектов в файл
    fn save_projects_index(&self) -> Result<(), ProjectError> {
        let projects: Vec<&ProjectMetadata> = self.projects.values().collect();
        let content = serde_json::to_string_pretty(&projects)?;
        fs::write(&self.projects_index_path, content)?;
        Ok(())
    }

    /// Получить список всех проектов
    pub fn list_projects(&self) -> Vec<ProjectMetadata> {
        self.projects.values().cloned().collect()
    }

    /// Зарегистрировать проект (после создания структуры через FileGateway)
    pub fn register_project(
        &mut self,
        name: &str,
        path: &str,
        file_gateway_id: &str,
    ) -> Result<ProjectMetadata, ProjectError> {
        // Проверяем, не зарегистрирован ли уже проект с таким путём
        if self.projects.values().any(|p| p.path == path) {
            return Err(ProjectError::ProjectAlreadyExists(path.to_string()));
        }

        let now = Utc::now();
        let id = Uuid::new_v4().to_string();

        let metadata = ProjectMetadata {
            id: id.clone(),
            name: name.to_string(),
            path: path.to_string(),
            file_gateway_id: file_gateway_id.to_string(),
            created_at: now,
            modified_at: now,
        };

        self.projects.insert(id, metadata.clone());
        self.save_projects_index()?;

        Ok(metadata)
    }

    /// Открыть проект по ID
    pub fn open_project(&mut self, project_id: &str) -> Result<ProjectMetadata, ProjectError> {
        let project = self
            .projects
            .get_mut(project_id)
            .ok_or_else(|| ProjectError::ProjectNotFound(project_id.to_string()))?;

        // Обновляем время последнего доступа
        project.modified_at = Utc::now();
        let result = project.clone();
        self.save_projects_index()?;

        Ok(result)
    }

    /// Удалить проект из реестра (не удаляет файлы)
    pub fn unregister_project(&mut self, project_id: &str) -> Result<(), ProjectError> {
        self.projects
            .remove(project_id)
            .ok_or_else(|| ProjectError::ProjectNotFound(project_id.to_string()))?;

        self.save_projects_index()?;
        Ok(())
    }
}
