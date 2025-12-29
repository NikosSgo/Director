"""API слой для связи с бэкендами."""

from app.api.gateway_client import GatewayClient

# Устаревшие клиенты (для обратной совместимости)
from app.api.engine_client import EngineClient
from app.api.file_gateway_client import FileGatewayClient

__all__ = ["GatewayClient", "EngineClient", "FileGatewayClient"]
