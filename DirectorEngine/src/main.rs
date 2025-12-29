mod project;

use tonic::transport::Server;
use tracing::info;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use project::service::ProjectServiceImpl;

pub mod proto {
    tonic::include_proto!("director");
}

use proto::project_service_server::ProjectServiceServer;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Инициализация логирования
    tracing_subscriber::registry()
        .with(tracing_subscriber::fmt::layer())
        .with(tracing_subscriber::EnvFilter::from_default_env())
        .init();

    let addr = "[::1]:50051".parse()?;
    let project_service = ProjectServiceImpl::new()?;

    info!("DirectorEngine gRPC сервер запущен на {}", addr);

    Server::builder()
        .add_service(ProjectServiceServer::new(project_service))
        .serve(addr)
        .await?;

    Ok(())
}
