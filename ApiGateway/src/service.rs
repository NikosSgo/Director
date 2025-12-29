//! Реализация API Gateway сервиса

use std::pin::Pin;
use std::sync::Arc;
use tokio::sync::Mutex;
use tokio_stream::{Stream, StreamExt};
use tonic::{Request, Response, Status, Streaming};
use tracing::{error, info};

use crate::clients::{EngineClient, FileClient};
use crate::proto::api_gateway::*;
use crate::proto::{director, file_gateway};

pub struct ApiGatewayImpl {
    engine: Arc<Mutex<EngineClient>>,
    file_gateway: Arc<Mutex<FileClient>>,
    version: String,
}

impl ApiGatewayImpl {
    pub async fn new(
        engine_address: String,
        file_gateway_address: String,
        version: String,
    ) -> Result<Self, Box<dyn std::error::Error + Send + Sync>> {
        let engine = EngineClient::connect(&engine_address).await?;
        let file_gateway = FileClient::connect(&file_gateway_address).await?;

        Ok(Self {
            engine: Arc::new(Mutex::new(engine)),
            file_gateway: Arc::new(Mutex::new(file_gateway)),
            version,
        })
    }
}

#[tonic::async_trait]
impl api_gateway_server::ApiGateway for ApiGatewayImpl {
    // === Health Check ===

    async fn health_check(
        &self,
        _request: Request<HealthCheckRequest>,
    ) -> Result<Response<HealthCheckResponse>, Status> {
        info!("Health check");

        let mut engine = self.engine.lock().await;
        let mut file_gw = self.file_gateway.lock().await;

        let (engine_ok, engine_latency) = engine.health_check().await;
        let (file_ok, file_latency) = file_gw.health_check().await;

        let services = vec![
            ServiceStatus {
                name: "DirectorEngine".to_string(),
                connected: engine_ok,
                address: engine.address.clone(),
                version: "0.1.0".to_string(),
                latency_ms: engine_latency,
            },
            ServiceStatus {
                name: "FileGateway".to_string(),
                connected: file_ok,
                address: file_gw.address.clone(),
                version: "0.1.0".to_string(),
                latency_ms: file_latency,
            },
        ];

        Ok(Response::new(HealthCheckResponse {
            all_healthy: engine_ok && file_ok,
            services,
        }))
    }

    async fn get_services_info(
        &self,
        _request: Request<GetServicesInfoRequest>,
    ) -> Result<Response<GetServicesInfoResponse>, Status> {
        info!("Get services info");

        let mut file_gw = self.file_gateway.lock().await;

        let storage_info = file_gw
            .client
            .get_storage_info(file_gateway::GetStorageInfoRequest {})
            .await
            .map_err(|e| Status::internal(format!("FileGateway error: {}", e)))?
            .into_inner();

        Ok(Response::new(GetServicesInfoResponse {
            gateway_version: self.version.clone(),
            engine_hostname: "localhost".to_string(), // TODO: получать от engine
            storage_hostname: storage_info.hostname,
            storage_os: storage_info.os,
            home_directory: storage_info.home_directory,
            default_projects_path: storage_info.default_projects_path,
            root_paths: storage_info.root_paths,
            total_space: storage_info.total_space,
            free_space: storage_info.free_space,
        }))
    }

    // === Проекты ===

    async fn list_projects(
        &self,
        _request: Request<ListProjectsRequest>,
    ) -> Result<Response<ListProjectsResponse>, Status> {
        let mut engine = self.engine.lock().await;

        let response = engine
            .client
            .list_projects(director::ListProjectsRequest {})
            .await
            .map_err(|e| Status::internal(format!("Engine error: {}", e)))?
            .into_inner();

        let projects = response
            .projects
            .into_iter()
            .map(|p| Project {
                id: p.id,
                name: p.name,
                path: p.path,
                created_at: p.created_at,
                updated_at: p.modified_at,
            })
            .collect();

        Ok(Response::new(ListProjectsResponse { projects }))
    }

    async fn create_project(
        &self,
        request: Request<CreateProjectRequest>,
    ) -> Result<Response<CreateProjectResponse>, Status> {
        let req = request.into_inner();
        info!("Create project: {} at {}", req.name, req.path);

        // 1. Создаём структуру папок через FileGateway
        let mut file_gw = self.file_gateway.lock().await;
        let structure = file_gw
            .client
            .init_project_structure(file_gateway::InitProjectStructureRequest {
                base_path: req.path.clone(),
                project_name: req.name.clone(),
            })
            .await
            .map_err(|e| Status::internal(format!("FileGateway error: {}", e)))?
            .into_inner();

        if !structure.success {
            return Ok(Response::new(CreateProjectResponse {
                success: false,
                error_message: structure.error_message,
                project: None,
            }));
        }

        drop(file_gw); // Освобождаем лок

        // 2. Регистрируем проект в DirectorEngine
        let mut engine = self.engine.lock().await;
        let response = engine
            .client
            .register_project(director::RegisterProjectRequest {
                name: req.name,
                path: structure.project_path,
                file_gateway_id: String::new(), // TODO: передавать ID
            })
            .await
            .map_err(|e| Status::internal(format!("Engine error: {}", e)))?
            .into_inner();

        let project = response.project.map(|p| Project {
            id: p.id,
            name: p.name,
            path: p.path,
            created_at: p.created_at,
            updated_at: p.modified_at,
        });

        Ok(Response::new(CreateProjectResponse {
            success: response.success,
            error_message: response.error_message,
            project,
        }))
    }

    async fn open_project(
        &self,
        request: Request<OpenProjectRequest>,
    ) -> Result<Response<OpenProjectResponse>, Status> {
        let req = request.into_inner();

        let mut engine = self.engine.lock().await;
        let response = engine
            .client
            .open_project(director::OpenProjectRequest {
                project_id: req.project_id,
            })
            .await
            .map_err(|e| Status::internal(format!("Engine error: {}", e)))?
            .into_inner();

        let project = response.project.map(|p| Project {
            id: p.id,
            name: p.name,
            path: p.path,
            created_at: p.created_at,
            updated_at: p.modified_at,
        });

        Ok(Response::new(OpenProjectResponse {
            success: response.success,
            error_message: response.error_message,
            project,
        }))
    }

    async fn delete_project(
        &self,
        request: Request<DeleteProjectRequest>,
    ) -> Result<Response<DeleteProjectResponse>, Status> {
        let req = request.into_inner();
        info!("Delete project: {}, delete_files: {}", req.project_id, req.delete_files);

        // Получаем информацию о проекте для удаления файлов
        let project_path = if req.delete_files {
            let mut engine = self.engine.lock().await;
            let list = engine
                .client
                .list_projects(director::ListProjectsRequest {})
                .await
                .map_err(|e| Status::internal(format!("Engine error: {}", e)))?
                .into_inner();

            list.projects
                .iter()
                .find(|p| p.id == req.project_id)
                .map(|p| p.path.clone())
        } else {
            None
        };

        // Удаляем из реестра
        let mut engine = self.engine.lock().await;
        let response = engine
            .client
            .unregister_project(director::UnregisterProjectRequest {
                project_id: req.project_id,
            })
            .await
            .map_err(|e| Status::internal(format!("Engine error: {}", e)))?
            .into_inner();

        drop(engine);

        // Удаляем файлы если нужно
        if response.success && req.delete_files {
            if let Some(path) = project_path {
                let mut file_gw = self.file_gateway.lock().await;
                if let Err(e) = file_gw
                    .client
                    .delete(file_gateway::DeleteRequest {
                        path,
                        recursive: true,
                    })
                    .await
                {
                    error!("Failed to delete project files: {}", e);
                }
            }
        }

        Ok(Response::new(DeleteProjectResponse {
            success: response.success,
            error_message: response.error_message,
        }))
    }

    // === Файловая система ===

    async fn get_storage_info(
        &self,
        _request: Request<GetStorageInfoRequest>,
    ) -> Result<Response<GetStorageInfoResponse>, Status> {
        let mut file_gw = self.file_gateway.lock().await;

        let response = file_gw
            .client
            .get_storage_info(file_gateway::GetStorageInfoRequest {})
            .await
            .map_err(|e| Status::internal(format!("FileGateway error: {}", e)))?
            .into_inner();

        Ok(Response::new(GetStorageInfoResponse {
            storage_id: response.storage_id,
            hostname: response.hostname,
            os: response.os,
            home_directory: response.home_directory,
            default_projects_path: response.default_projects_path,
            root_paths: response.root_paths,
            total_space: response.total_space,
            free_space: response.free_space,
        }))
    }

    async fn browse_directory(
        &self,
        request: Request<BrowseDirectoryRequest>,
    ) -> Result<Response<BrowseDirectoryResponse>, Status> {
        let req = request.into_inner();

        let mut file_gw = self.file_gateway.lock().await;
        let response = file_gw
            .client
            .browse_directory(file_gateway::BrowseDirectoryRequest { path: req.path })
            .await
            .map_err(|e| Status::internal(format!("FileGateway error: {}", e)))?
            .into_inner();

        let entries = response
            .entries
            .into_iter()
            .map(|e| DirectoryEntry {
                name: e.name,
                path: e.path,
                is_directory: e.is_directory,
                size: e.size,
                created_at: e.created_at,
                modified_at: e.modified_at,
                mime_type: e.mime_type,
            })
            .collect();

        Ok(Response::new(BrowseDirectoryResponse {
            success: response.success,
            error_message: response.error_message,
            current_path: response.current_path,
            parent_path: response.parent_path,
            entries,
        }))
    }

    async fn create_directory(
        &self,
        request: Request<CreateDirectoryRequest>,
    ) -> Result<Response<CreateDirectoryResponse>, Status> {
        let req = request.into_inner();

        let mut file_gw = self.file_gateway.lock().await;
        let response = file_gw
            .client
            .create_directory(file_gateway::CreateDirectoryRequest {
                path: req.path,
                create_parents: req.create_parents,
            })
            .await
            .map_err(|e| Status::internal(format!("FileGateway error: {}", e)))?
            .into_inner();

        Ok(Response::new(CreateDirectoryResponse {
            success: response.success,
            error_message: response.error_message,
            created_path: response.created_path,
        }))
    }

    async fn delete(
        &self,
        request: Request<DeleteRequest>,
    ) -> Result<Response<DeleteResponse>, Status> {
        let req = request.into_inner();

        let mut file_gw = self.file_gateway.lock().await;
        let response = file_gw
            .client
            .delete(file_gateway::DeleteRequest {
                path: req.path,
                recursive: req.recursive,
            })
            .await
            .map_err(|e| Status::internal(format!("FileGateway error: {}", e)))?
            .into_inner();

        Ok(Response::new(DeleteResponse {
            success: response.success,
            error_message: response.error_message,
        }))
    }

    async fn init_project_structure(
        &self,
        request: Request<InitProjectStructureRequest>,
    ) -> Result<Response<InitProjectStructureResponse>, Status> {
        let req = request.into_inner();

        let mut file_gw = self.file_gateway.lock().await;
        let response = file_gw
            .client
            .init_project_structure(file_gateway::InitProjectStructureRequest {
                base_path: req.base_path,
                project_name: req.project_name,
            })
            .await
            .map_err(|e| Status::internal(format!("FileGateway error: {}", e)))?
            .into_inner();

        Ok(Response::new(InitProjectStructureResponse {
            success: response.success,
            error_message: response.error_message,
            project_path: response.project_path,
            assets_path: response.assets_path,
            video_path: response.video_path,
            audio_path: response.audio_path,
            images_path: response.images_path,
            timeline_path: response.timeline_path,
            exports_path: response.exports_path,
        }))
    }

    // === Стриминг файлов ===

    async fn upload_file(
        &self,
        request: Request<Streaming<UploadFileRequest>>,
    ) -> Result<Response<UploadFileResponse>, Status> {
        let mut stream = request.into_inner();
        let mut file_gw = self.file_gateway.lock().await;

        // Преобразуем стрим
        let mapped_stream = async_stream::stream! {
            while let Some(msg) = stream.next().await {
                match msg {
                    Ok(req) => {
                        let fg_req = match req.data {
                            Some(upload_file_request::Data::Metadata(m)) => {
                                file_gateway::UploadFileRequest {
                                    data: Some(file_gateway::upload_file_request::Data::Metadata(
                                        file_gateway::UploadFileMetadata {
                                            destination_path: m.destination_path,
                                            filename: m.filename,
                                            total_size: m.total_size,
                                            overwrite: m.overwrite,
                                        },
                                    )),
                                }
                            }
                            Some(upload_file_request::Data::Chunk(c)) => {
                                file_gateway::UploadFileRequest {
                                    data: Some(file_gateway::upload_file_request::Data::Chunk(c)),
                                }
                            }
                            None => continue,
                        };
                        yield fg_req;
                    }
                    Err(_) => break,
                }
            }
        };

        let response = file_gw
            .client
            .upload_file(mapped_stream)
            .await
            .map_err(|e| Status::internal(format!("FileGateway error: {}", e)))?
            .into_inner();

        Ok(Response::new(UploadFileResponse {
            success: response.success,
            error_message: response.error_message,
            file_path: response.file_path,
            bytes_written: response.bytes_written,
        }))
    }

    type DownloadFileStream = Pin<Box<dyn Stream<Item = Result<DownloadFileResponse, Status>> + Send>>;

    async fn download_file(
        &self,
        request: Request<DownloadFileRequest>,
    ) -> Result<Response<Self::DownloadFileStream>, Status> {
        let req = request.into_inner();
        let mut file_gw = self.file_gateway.lock().await;

        let response = file_gw
            .client
            .download_file(file_gateway::DownloadFileRequest { path: req.path })
            .await
            .map_err(|e| Status::internal(format!("FileGateway error: {}", e)))?;

        let mut inner_stream = response.into_inner();

        let output_stream = async_stream::try_stream! {
            while let Some(msg) = inner_stream.next().await {
                let msg = msg.map_err(|e| Status::internal(format!("Stream error: {}", e)))?;
                
                let response = match msg.data {
                    Some(file_gateway::download_file_response::Data::Metadata(m)) => {
                        DownloadFileResponse {
                            data: Some(download_file_response::Data::Metadata(
                                DownloadFileMetadata {
                                    filename: m.filename,
                                    total_size: m.total_size,
                                    mime_type: m.mime_type,
                                },
                            )),
                        }
                    }
                    Some(file_gateway::download_file_response::Data::Chunk(c)) => {
                        DownloadFileResponse {
                            data: Some(download_file_response::Data::Chunk(c)),
                        }
                    }
                    None => continue,
                };
                yield response;
            }
        };

        Ok(Response::new(Box::pin(output_stream)))
    }
}

