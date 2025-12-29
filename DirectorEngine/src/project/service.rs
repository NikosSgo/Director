use std::sync::Mutex;
use tonic::{Request, Response, Status};
use tracing::{error, info};

use crate::project::manager::{ProjectError, ProjectManager, ProjectMetadata};
use crate::proto::{
    project_service_server::ProjectService,
    GetEngineInfoRequest, GetEngineInfoResponse,
    ListProjectsRequest, ListProjectsResponse,
    OpenProjectRequest, OpenProjectResponse,
    ProjectInfo, RegisterProjectRequest, RegisterProjectResponse,
    UnregisterProjectRequest, UnregisterProjectResponse,
};

const ENGINE_VERSION: &str = env!("CARGO_PKG_VERSION");

pub struct ProjectServiceImpl {
    manager: Mutex<ProjectManager>,
    engine_id: String,
}

impl ProjectServiceImpl {
    pub fn new() -> Result<Self, ProjectError> {
        Ok(Self {
            manager: Mutex::new(ProjectManager::new()?),
            engine_id: uuid::Uuid::new_v4().to_string(),
        })
    }
}

impl From<&ProjectMetadata> for ProjectInfo {
    fn from(meta: &ProjectMetadata) -> Self {
        ProjectInfo {
            id: meta.id.clone(),
            name: meta.name.clone(),
            path: meta.path.clone(),
            file_gateway_id: meta.file_gateway_id.clone(),
            created_at: meta.created_at.timestamp(),
            modified_at: meta.modified_at.timestamp(),
        }
    }
}

#[tonic::async_trait]
impl ProjectService for ProjectServiceImpl {
    async fn get_engine_info(
        &self,
        _request: Request<GetEngineInfoRequest>,
    ) -> Result<Response<GetEngineInfoResponse>, Status> {
        info!("Запрос информации о движке");

        Ok(Response::new(GetEngineInfoResponse {
            engine_id: self.engine_id.clone(),
            version: ENGINE_VERSION.to_string(),
            supported_formats: vec![
                "mp4".to_string(),
                "mov".to_string(),
                "avi".to_string(),
                "mkv".to_string(),
                "webm".to_string(),
            ],
        }))
    }

    async fn list_projects(
        &self,
        _request: Request<ListProjectsRequest>,
    ) -> Result<Response<ListProjectsResponse>, Status> {
        info!("Запрос списка проектов");

        let manager = self.manager.lock().map_err(|e| {
            error!("Ошибка блокировки менеджера: {}", e);
            Status::internal("Внутренняя ошибка сервера")
        })?;

        let projects: Vec<ProjectInfo> = manager
            .list_projects()
            .iter()
            .map(ProjectInfo::from)
            .collect();

        Ok(Response::new(ListProjectsResponse { projects }))
    }

    async fn register_project(
        &self,
        request: Request<RegisterProjectRequest>,
    ) -> Result<Response<RegisterProjectResponse>, Status> {
        let req = request.into_inner();
        info!(
            "Регистрация проекта: {} в {} (gateway: {})",
            req.name, req.path, req.file_gateway_id
        );

        let mut manager = self.manager.lock().map_err(|e| {
            error!("Ошибка блокировки менеджера: {}", e);
            Status::internal("Внутренняя ошибка сервера")
        })?;

        match manager.register_project(&req.name, &req.path, &req.file_gateway_id) {
            Ok(metadata) => Ok(Response::new(RegisterProjectResponse {
                success: true,
                error_message: String::new(),
                project: Some(ProjectInfo::from(&metadata)),
            })),
            Err(e) => {
                error!("Ошибка регистрации проекта: {}", e);
                Ok(Response::new(RegisterProjectResponse {
                    success: false,
                    error_message: e.to_string(),
                    project: None,
                }))
            }
        }
    }

    async fn open_project(
        &self,
        request: Request<OpenProjectRequest>,
    ) -> Result<Response<OpenProjectResponse>, Status> {
        let req = request.into_inner();
        info!("Открытие проекта: {}", req.project_id);

        let mut manager = self.manager.lock().map_err(|e| {
            error!("Ошибка блокировки менеджера: {}", e);
            Status::internal("Внутренняя ошибка сервера")
        })?;

        match manager.open_project(&req.project_id) {
            Ok(metadata) => Ok(Response::new(OpenProjectResponse {
                success: true,
                error_message: String::new(),
                project: Some(ProjectInfo::from(&metadata)),
            })),
            Err(e) => {
                error!("Ошибка открытия проекта: {}", e);
                Ok(Response::new(OpenProjectResponse {
                    success: false,
                    error_message: e.to_string(),
                    project: None,
                }))
            }
        }
    }

    async fn unregister_project(
        &self,
        request: Request<UnregisterProjectRequest>,
    ) -> Result<Response<UnregisterProjectResponse>, Status> {
        let req = request.into_inner();
        info!("Удаление проекта из реестра: {}", req.project_id);

        let mut manager = self.manager.lock().map_err(|e| {
            error!("Ошибка блокировки менеджера: {}", e);
            Status::internal("Внутренняя ошибка сервера")
        })?;

        match manager.unregister_project(&req.project_id) {
            Ok(()) => Ok(Response::new(UnregisterProjectResponse {
                success: true,
                error_message: String::new(),
            })),
            Err(e) => {
                error!("Ошибка удаления проекта: {}", e);
                Ok(Response::new(UnregisterProjectResponse {
                    success: false,
                    error_message: e.to_string(),
                }))
            }
        }
    }
}
