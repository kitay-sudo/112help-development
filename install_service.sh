#!/bin/bash

# 112help - Установка службы Ubuntu
# Скрипт для установки Telegram-бота как системной службы

set -e

echo "========================================"
echo "  112help - Установка Ubuntu службы"
echo "========================================"
echo

# Проверка прав root
if [[ $EUID -ne 0 ]]; then
   echo "[ОШИБКА] Этот скрипт должен запускаться с правами root"
   echo "Используйте: sudo ./install_service.sh"
   exit 1
fi

echo "[OK] Запущено с правами root"

# Переменные
SERVICE_NAME="112help"
SERVICE_USER="112help"
SERVICE_GROUP="112help"
INSTALL_DIR="/opt/112help"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
CURRENT_DIR=$(pwd)

echo "Текущая директория: $CURRENT_DIR"
echo "Директория установки: $INSTALL_DIR"

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "[ОШИБКА] Python3 не найден"
    echo "Установите Python3: sudo apt update && sudo apt install python3 python3-pip"
    exit 1
fi

echo "[OK] Python3 найден: $(python3 --version)"

# Проверка pip
if ! command -v pip3 &> /dev/null; then
    echo "[ОШИБКА] pip3 не найден"
    echo "Установите pip3: sudo apt install python3-pip"
    exit 1
fi

echo "[OK] pip3 найден"

# Проверка main.py
if [[ ! -f "$CURRENT_DIR/main.py" ]]; then
    echo "[ОШИБКА] Файл main.py не найден в $CURRENT_DIR"
    exit 1
fi

echo "[OK] main.py найден"

# Проверка requirements.txt
if [[ ! -f "$CURRENT_DIR/requirements.txt" ]]; then
    echo "[ОШИБКА] Файл requirements.txt не найден в $CURRENT_DIR"
    exit 1
fi

echo "[OK] requirements.txt найден"

# Создание пользователя для службы
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "Создание пользователя $SERVICE_USER..."
    useradd --system --no-create-home --shell /bin/false "$SERVICE_USER"
    echo "[OK] Пользователь $SERVICE_USER создан"
else
    echo "[OK] Пользователь $SERVICE_USER уже существует"
fi

# Создание директории установки
echo "Создание директории $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/logs"

# Копирование файлов
echo "Копирование файлов проекта..."
cp -r "$CURRENT_DIR"/* "$INSTALL_DIR/"

# Установка зависимостей Python
echo "Установка зависимостей Python..."
cd "$INSTALL_DIR"
pip3 install -r requirements.txt

# Настройка прав доступа
echo "Настройка прав доступа..."
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR/logs"

# Проверка .env файла
if [[ ! -f "$INSTALL_DIR/.env" ]]; then
    echo "[ПРЕДУПРЕЖДЕНИЕ] Файл .env не найден"
    echo "Создание примера конфигурации..."
    
    if [[ -f "$INSTALL_DIR/config.env.example" ]]; then
        cp "$INSTALL_DIR/config.env.example" "$INSTALL_DIR/.env"
        echo "[OK] Создан .env из config.env.example"
        echo "[ВАЖНО] Отредактируйте $INSTALL_DIR/.env с вашими настройками"
    else
        cat > "$INSTALL_DIR/.env" << EOF
# Токен Telegram бота
BOT_TOKEN=your_bot_token_here

# Подключение к MongoDB (опционально)
MONGODB_URL=disabled
DATABASE_NAME=emergency_bot

# ID администраторов (через запятую)
ADMIN_IDS=123456789

# OpenAI API ключ (опционально)
OPENAI_API_KEY=your_openai_api_key_here

# Настройки логирования
LOG_LEVEL=INFO
ENVIRONMENT=production
EOF
        echo "[OK] Создан базовый .env файл"
        echo "[ВАЖНО] Отредактируйте $INSTALL_DIR/.env с вашими настройками"
    fi
fi

# Копирование systemd unit файла
echo "Установка systemd service..."
cp "$CURRENT_DIR/112help.service" "$SERVICE_FILE"

# Перезагрузка systemd
echo "Перезагрузка systemd daemon..."
systemctl daemon-reload

# Включение службы в автозагрузку
echo "Включение службы в автозагрузку..."
systemctl enable "$SERVICE_NAME"

# Запуск службы
echo "Запуск службы..."
systemctl start "$SERVICE_NAME"

# Проверка статуса
sleep 2
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "[OK] Служба запущена успешно"
else
    echo "[ПРЕДУПРЕЖДЕНИЕ] Служба может не запуститься"
    echo "Проверьте настройки в $INSTALL_DIR/.env"
fi

echo
echo "========================================"
echo "   Установка завершена!"
echo "========================================"
echo
echo "Управление службой:"
echo "  Статус:      sudo systemctl status $SERVICE_NAME"
echo "  Запуск:      sudo systemctl start $SERVICE_NAME"
echo "  Остановка:   sudo systemctl stop $SERVICE_NAME"
echo "  Перезапуск:  sudo systemctl restart $SERVICE_NAME"
echo "  Логи:        sudo journalctl -u $SERVICE_NAME -f"
echo
echo "Файлы службы:"
echo "  Конфигурация: $INSTALL_DIR/.env"
echo "  Логи:         $INSTALL_DIR/logs/"
echo "  Service:      $SERVICE_FILE"
echo
echo "ВАЖНО: Отредактируйте $INSTALL_DIR/.env с вашими настройками!"
echo
echo "Для удаления службы запустите: sudo ./uninstall_service.sh" 