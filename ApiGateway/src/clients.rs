//! Клиенты для подключения к внутренним сервисам

use std::time::{Duration, Instant};
use tonic::transport::Channel;
use tracing::{error, info};

use crate::proto::director::project_service_client::ProjectServiceClient;
use crate::proto::file_gateway::file_gateway_client::FileGatewayClient;

/// Клиент для DirectorEngine
pub struct EngineClient {
    pub client: ProjectServiceClient<Channel>,
    pub address: String,
}

impl EngineClient {
    pub async fn connect(address: &str) -> Result<Self, Box<dyn std::error::Error + Send + Sync>> {
        let channel = Channel::from_shared(address.to_string())?
            .connect_timeout(Duration::from_secs(5))
            .connect()
            .await?;

        info!("Подключён к DirectorEngine: {}", address);

        Ok(Self {
            client: ProjectServiceClient::new(channel),
            address: address.to_string(),
        })
    }

    pub async fn health_check(&mut self) -> (bool, i64) {
        let start = Instant::now();
        
        match self.client.list_projects(crate::proto::director::ListProjectsRequest {}).await {
            Ok(_) => (true, start.elapsed().as_millis() as i64),
            Err(e) => {
                error!("DirectorEngine health check failed: {}", e);
                (false, -1)
            }
        }
    }
}

/// Клиент для FileGateway
pub struct FileClient {
    pub client: FileGatewayClient<Channel>,
    pub address: String,
}

impl FileClient {
    pub async fn connect(address: &str) -> Result<Self, Box<dyn std::error::Error + Send + Sync>> {
        let channel = Channel::from_shared(address.to_string())?
            .connect_timeout(Duration::from_secs(5))
            .connect()
            .await?;

        info!("Подключён к FileGateway: {}", address);

        Ok(Self {
            client: FileGatewayClient::new(channel),
            address: address.to_string(),
        })
    }

    pub async fn health_check(&mut self) -> (bool, i64) {
        let start = Instant::now();
        
        match self.client.get_storage_info(crate::proto::file_gateway::GetStorageInfoRequest {}).await {
            Ok(_) => (true, start.elapsed().as_millis() as i64),
            Err(e) => {
                error!("FileGateway health check failed: {}", e);
                (false, -1)
            }
        }
    }
}

