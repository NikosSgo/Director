mod service;
mod storage;

use tonic::transport::Server;
use tracing::info;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use service::FileGatewayImpl;

pub mod proto {
    tonic::include_proto!("file_gateway");
}

use proto::file_gateway_server::FileGatewayServer;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Инициализация логирования
    tracing_subscriber::registry()
        .with(tracing_subscriber::fmt::layer())
        .with(tracing_subscriber::EnvFilter::from_default_env())
        .init();

    let addr = "[::1]:50052".parse()?;
    
    // Создаём сервис с локальным провайдером (по умолчанию)
    let file_gateway = FileGatewayImpl::new()?;

    info!("FileGateway gRPC сервер запущен на {}", addr);
    info!("Используется провайдер: LocalStorageProvider");

    Server::builder()
        .add_service(FileGatewayServer::new(file_gateway))
        .serve(addr)
        .await?;

    Ok(())
}
