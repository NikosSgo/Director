#!/bin/bash
# Скрипт генерации Python кода из proto файлов

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PROTO_DIR="$(dirname "$PROJECT_ROOT")/proto"
OUTPUT_DIR="$PROJECT_ROOT/src/app/api/proto"

echo "Генерация Python кода из proto файлов..."
echo "Proto директория: $PROTO_DIR"
echo "Выходная директория: $OUTPUT_DIR"

# Создаём выходную директорию
mkdir -p "$OUTPUT_DIR"

# Генерируем код используя uv run
cd "$PROJECT_ROOT"
uv run python -m grpc_tools.protoc \
    -I"$PROTO_DIR" \
    --python_out="$OUTPUT_DIR" \
    --grpc_python_out="$OUTPUT_DIR" \
    "$PROTO_DIR/director.proto"

# Исправляем импорты для Python 3
sed -i 's/import director_pb2/from app.api.proto import director_pb2/' "$OUTPUT_DIR/director_pb2_grpc.py"

echo "Готово!"
