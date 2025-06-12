#!/bin/bash

# 112help - Удаление службы Ubuntu
# Скрипт для удаления системной службы

set -e

echo "========================================"
echo "  112help - Удаление Ubuntu службы"
echo "========================================"
echo

# Проверка прав root
if [[ $EUID -ne 0 ]]; then
   echo "[ОШИБКА] Этот скрипт должен запускаться с правами root"
   echo "Используйте: sudo ./uninstall_service.sh"
   exit 1
fi

echo "[OK] Запущено с правами root"

# Переменные
SERVICE_NAME="112help"
SERVICE_USER="112help"
INSTALL_DIR="/opt/112help"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# Проверка существования службы
if [[ ! -f "$SERVICE_FILE" ]]; then
    echo "[ИНФО] Файл службы $SERVICE_FILE не найден"
    echo "Возможно служба уже удалена"
else
    echo "[ИНФО] Служба $SERVICE_NAME найдена"
    
    # Остановка службы
    echo "Остановка службы..."
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        systemctl stop "$SERVICE_NAME"
        echo "[OK] Служба остановлена"
    else
        echo "[OK] Служба уже остановлена"
    fi
    
    # Отключение автозагрузки
    echo "Отключение автозагрузки..."
    if systemctl is-enabled --quiet "$SERVICE_NAME"; then
        systemctl disable "$SERVICE_NAME"
        echo "[OK] Автозагрузка отключена"
    else
        echo "[OK] Автозагрузка уже отключена"
    fi
    
    # Удаление файла службы
    echo "Удаление файла службы..."
    rm -f "$SERVICE_FILE"
    echo "[OK] Файл службы удален"
    
    # Перезагрузка systemd
    echo "Перезагрузка systemd daemon..."
    systemctl daemon-reload
    systemctl reset-failed
    echo "[OK] systemd обновлен"
fi

# Вопрос об удалении файлов
echo
read -p "Удалить файлы приложения в $INSTALL_DIR? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [[ -d "$INSTALL_DIR" ]]; then
        echo "Удаление $INSTALL_DIR..."
        rm -rf "$INSTALL_DIR"
        echo "[OK] Файлы приложения удалены"
    else
        echo "[OK] Директория $INSTALL_DIR не найдена"
    fi
else
    echo "[OK] Файлы приложения сохранены в $INSTALL_DIR"
fi

# Вопрос об удалении пользователя
echo
read -p "Удалить пользователя $SERVICE_USER? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if id "$SERVICE_USER" &>/dev/null; then
        echo "Удаление пользователя $SERVICE_USER..."
        userdel "$SERVICE_USER" 2>/dev/null || true
        echo "[OK] Пользователь удален"
    else
        echo "[OK] Пользователь $SERVICE_USER не найден"
    fi
else
    echo "[OK] Пользователь $SERVICE_USER сохранен"
fi

echo
echo "========================================"
echo "   Удаление завершено!"
echo "========================================"
echo
echo "Служба $SERVICE_NAME полностью удалена из системы"
echo 