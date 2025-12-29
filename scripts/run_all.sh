#!/bin/bash

# ===========================================
# Скрипт запуска всех сервисов Director
# ===========================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Проверка зависимостей
check_dependencies() {
    log_info "Проверка зависимостей..."
    
    if ! command -v cargo &> /dev/null; then
        log_error "cargo не найден. Установите Rust: https://rustup.rs/"
        exit 1
    fi
    
    if ! command -v uv &> /dev/null; then
        log_error "uv не найден. Установите: pip install uv"
        exit 1
    fi
    
    log_success "Все зависимости найдены"
}

# Сборка Rust проектов
build_rust() {
    log_info "Сборка Rust проектов..."
    
    log_info "  Сборка DirectorEngine..."
    (cd DirectorEngine && cargo build --release 2>&1 | tail -1)
    
    log_info "  Сборка FileGateway..."
    (cd FileGateway && cargo build --release 2>&1 | tail -1)
    
    log_info "  Сборка ApiGateway..."
    (cd ApiGateway && cargo build --release 2>&1 | tail -1)
    
    log_success "Rust проекты собраны"
}

# Генерация Python proto
generate_proto() {
    log_info "Генерация Python protobuf..."
    
    cd Director/src
    uv run python -m grpc_tools.protoc \
        -I../../proto \
        --python_out=app/api/proto \
        --grpc_python_out=app/api/proto \
        ../../proto/director.proto \
        ../../proto/file_gateway.proto \
        ../../proto/api_gateway.proto
    cd ../..
    
    log_success "Protobuf сгенерирован"
}

# Освобождение портов
free_ports() {
    log_info "Проверка портов..."
    
    for port in 50050 50051 50052; do
        pid=$(lsof -ti :$port 2>/dev/null || true)
        if [ -n "$pid" ]; then
            log_warn "Порт $port занят (PID: $pid), освобождаю..."
            kill -9 $pid 2>/dev/null || true
            sleep 1
        fi
    done
    
    log_success "Порты свободны"
}

# Запуск сервисов
start_services() {
    log_info "Запуск сервисов..."
    
    # DirectorEngine (порт 50051)
    log_info "  Запуск DirectorEngine на :50051..."
    RUST_LOG=info ./DirectorEngine/target/release/director-engine &
    ENGINE_PID=$!
    sleep 1
    
    # FileGateway (порт 50052)
    log_info "  Запуск FileGateway на :50052..."
    RUST_LOG=info ./FileGateway/target/release/file-gateway &
    FILE_GW_PID=$!
    sleep 1
    
    # ApiGateway (порт 50050)
    log_info "  Запуск ApiGateway на :50050..."
    RUST_LOG=info ./ApiGateway/target/release/api-gateway &
    API_GW_PID=$!
    sleep 2
    
    log_success "Все сервисы запущены"
    echo ""
    log_info "PIDs: Engine=$ENGINE_PID, FileGW=$FILE_GW_PID, ApiGW=$API_GW_PID"
}

# Запуск GUI
start_gui() {
    log_info "Запуск Director GUI..."
    echo ""
    
    cd Director/src
    uv run python main.py
    cd ../..
}

# Остановка сервисов
stop_services() {
    echo ""
    log_info "Остановка сервисов..."
    
    pkill -f "director-engine" 2>/dev/null || true
    pkill -f "file-gateway" 2>/dev/null || true
    pkill -f "api-gateway" 2>/dev/null || true
    
    log_success "Все сервисы остановлены"
}

# Обработка Ctrl+C
trap stop_services EXIT

# Главная функция
main() {
    echo ""
    echo "=========================================="
    echo "       Director - Video Editor           "
    echo "=========================================="
    echo ""
    
    check_dependencies
    build_rust
    generate_proto
    free_ports
    start_services
    
    echo ""
    echo "=========================================="
    echo "  API Gateway доступен на localhost:50050"
    echo "=========================================="
    echo ""
    
    start_gui
}

main "$@"
