mod service;
mod clients;

use tonic::transport::Server;
use tracing::info;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use service::ApiGatewayImpl;

pub mod proto {
    pub mod api_gateway {
        tonic::include_proto!("api_gateway");
    }
    pub mod director {
        tonic::include_proto!("director");
    }
    pub mod file_gateway {
        tonic::include_proto!("file_gateway");
    }
}

use proto::api_gateway::api_gateway_server::ApiGatewayServer;

const GATEWAY_VERSION: &str = env!("CARGO_PKG_VERSION");
const GATEWAY_PORT: u16 = 50050;
const ENGINE_ADDRESS: &str = "http://[::1]:50051";
const FILE_GATEWAY_ADDRESS: &str = "http://[::1]:50052";

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    tracing_subscriber::registry()
        .with(tracing_subscriber::fmt::layer())
        .with(tracing_subscriber::EnvFilter::from_default_env())
        .init();

    let addr = format!("[::1]:{}", GATEWAY_PORT).parse()?;

    info!("Подключение к DirectorEngine: {}", ENGINE_ADDRESS);
    info!("Подключение к FileGateway: {}", FILE_GATEWAY_ADDRESS);

    let gateway = ApiGatewayImpl::new(
        ENGINE_ADDRESS.to_string(),
        FILE_GATEWAY_ADDRESS.to_string(),
        GATEWAY_VERSION.to_string(),
    ).await?;

    info!("API Gateway v{} запущен на {}", GATEWAY_VERSION, addr);

    Server::builder()
        .add_service(ApiGatewayServer::new(gateway))
        .serve(addr)
        .await?;

    Ok(())
}

