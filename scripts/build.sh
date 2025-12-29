#!/bin/bash
# ===========================================
# Director - Скрипт сборки проекта
# ===========================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Сборка проекта Director${NC}"
echo

# DirectorEngine
echo -e "${BLUE}[1/3]${NC} Сборка DirectorEngine..."
cd "$PROJECT_ROOT/DirectorEngine"
cargo build --release
echo -e "${GREEN}✓ DirectorEngine${NC}"

# FileGateway
echo -e "${BLUE}[2/3]${NC} Сборка FileGateway..."
cd "$PROJECT_ROOT/FileGateway"
cargo build --release
echo -e "${GREEN}✓ FileGateway${NC}"

# Python зависимости и protobuf
echo -e "${BLUE}[3/3]${NC} Настройка Python..."
cd "$PROJECT_ROOT/Director"
uv sync

# Генерируем protobuf
uv run python -m grpc_tools.protoc \
    -I"$PROJECT_ROOT/proto" \
    --python_out=src/app/api/proto \
    --grpc_python_out=src/app/api/proto \
    "$PROJECT_ROOT/proto/director.proto" \
    "$PROJECT_ROOT/proto/file_gateway.proto"

sed -i 's/import director_pb2/from app.api.proto import director_pb2/' src/app/api/proto/director_pb2_grpc.py
sed -i 's/import file_gateway_pb2/from app.api.proto import file_gateway_pb2/' src/app/api/proto/file_gateway_pb2_grpc.py

echo -e "${GREEN}✓ Python${NC}"

echo
echo -e "${GREEN}Сборка завершена!${NC}"
echo
echo "Запуск: ./scripts/run_all.sh"

