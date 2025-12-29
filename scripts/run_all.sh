#!/bin/bash
# ===========================================
# Director - Скрипт запуска всех сервисов
# ===========================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Director - Запуск проекта        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo

# Функция для проверки порта
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # Порт занят
    else
        return 1  # Порт свободен
    fi
}

# Функция для остановки процесса на порту
kill_port() {
    local port=$1
    local pid=$(lsof -Pi :$port -sTCP:LISTEN -t 2>/dev/null)
    if [ -n "$pid" ]; then
        echo -e "${YELLOW}Останавливаем процесс на порту $port (PID: $pid)${NC}"
        kill $pid 2>/dev/null || true
        sleep 1
    fi
}

# Функция для cleanup при выходе
cleanup() {
    echo
    echo -e "${YELLOW}Останавливаем сервисы...${NC}"
    
    # Останавливаем фоновые процессы
    if [ -n "$ENGINE_PID" ]; then
        kill $ENGINE_PID 2>/dev/null || true
    fi
    if [ -n "$FILE_GATEWAY_PID" ]; then
        kill $FILE_GATEWAY_PID 2>/dev/null || true
    fi
    
    # Ждём завершения
    wait 2>/dev/null || true
    
    echo -e "${GREEN}Все сервисы остановлены${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Проверяем зависимости
echo -e "${BLUE}[1/5]${NC} Проверка зависимостей..."

if ! command -v cargo &> /dev/null; then
    echo -e "${RED}Ошибка: cargo не найден. Установите Rust.${NC}"
    exit 1
fi

if ! command -v uv &> /dev/null; then
    echo -e "${RED}Ошибка: uv не найден. Установите uv (pip install uv).${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Все зависимости найдены${NC}"
echo

# Собираем Rust проекты
echo -e "${BLUE}[2/5]${NC} Сборка DirectorEngine..."
cd "$PROJECT_ROOT/DirectorEngine"
cargo build --release 2>&1 | tail -3
echo -e "${GREEN}✓ DirectorEngine собран${NC}"
echo

echo -e "${BLUE}[3/5]${NC} Сборка FileGateway..."
cd "$PROJECT_ROOT/FileGateway"
cargo build --release 2>&1 | tail -3
echo -e "${GREEN}✓ FileGateway собран${NC}"
echo

# Генерируем protobuf для Python
echo -e "${BLUE}[4/5]${NC} Генерация Python protobuf..."
cd "$PROJECT_ROOT/Director"
uv sync --quiet
uv run python -m grpc_tools.protoc \
    -I"$PROJECT_ROOT/proto" \
    --python_out=src/app/api/proto \
    --grpc_python_out=src/app/api/proto \
    "$PROJECT_ROOT/proto/director.proto" \
    "$PROJECT_ROOT/proto/file_gateway.proto"

# Исправляем импорты
sed -i 's/import director_pb2/from app.api.proto import director_pb2/' src/app/api/proto/director_pb2_grpc.py
sed -i 's/import file_gateway_pb2/from app.api.proto import file_gateway_pb2/' src/app/api/proto/file_gateway_pb2_grpc.py
echo -e "${GREEN}✓ Protobuf сгенерирован${NC}"
echo

# Освобождаем порты если заняты
if check_port 50051; then
    kill_port 50051
fi
if check_port 50052; then
    kill_port 50052
fi

# Запускаем сервисы
echo -e "${BLUE}[5/5]${NC} Запуск сервисов..."
echo

# DirectorEngine
echo -e "${YELLOW}→ Запуск DirectorEngine на порту 50051...${NC}"
cd "$PROJECT_ROOT/DirectorEngine"
RUST_LOG=info ./target/release/director-engine &
ENGINE_PID=$!
sleep 1

if kill -0 $ENGINE_PID 2>/dev/null; then
    echo -e "${GREEN}✓ DirectorEngine запущен (PID: $ENGINE_PID)${NC}"
else
    echo -e "${RED}✗ Ошибка запуска DirectorEngine${NC}"
    exit 1
fi

# FileGateway
echo -e "${YELLOW}→ Запуск FileGateway на порту 50052...${NC}"
cd "$PROJECT_ROOT/FileGateway"
RUST_LOG=info ./target/release/file-gateway &
FILE_GATEWAY_PID=$!
sleep 1

if kill -0 $FILE_GATEWAY_PID 2>/dev/null; then
    echo -e "${GREEN}✓ FileGateway запущен (PID: $FILE_GATEWAY_PID)${NC}"
else
    echo -e "${RED}✗ Ошибка запуска FileGateway${NC}"
    exit 1
fi

echo
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Все сервисы успешно запущены!      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo
echo -e "  ${BLUE}DirectorEngine${NC}: http://localhost:50051"
echo -e "  ${BLUE}FileGateway${NC}:    http://localhost:50052"
echo
echo -e "${YELLOW}Запуск GUI клиента...${NC}"
echo

# Запускаем GUI
cd "$PROJECT_ROOT/Director/src"
uv run python main.py

# После закрытия GUI выполняем cleanup
cleanup

