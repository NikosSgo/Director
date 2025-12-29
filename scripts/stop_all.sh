#!/bin/bash
# ===========================================
# Director - Скрипт остановки всех сервисов
# ===========================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Останавливаем сервисы Director...${NC}"

# Останавливаем DirectorEngine
if pkill -f "director-engine" 2>/dev/null; then
    echo -e "${GREEN}✓ DirectorEngine остановлен${NC}"
else
    echo -e "${YELLOW}DirectorEngine не был запущен${NC}"
fi

# Останавливаем FileGateway
if pkill -f "file-gateway" 2>/dev/null; then
    echo -e "${GREEN}✓ FileGateway остановлен${NC}"
else
    echo -e "${YELLOW}FileGateway не был запущен${NC}"
fi

echo -e "${GREEN}Готово!${NC}"

