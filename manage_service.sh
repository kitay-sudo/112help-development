#!/bin/bash

# 112help - Управление службой Ubuntu
# Интерактивный скрипт для управления системной службой

SERVICE_NAME="112help"
INSTALL_DIR="/opt/112help"

echo "========================================"
echo "  112help - Управление Ubuntu службой"
echo "========================================"

# Функция для проверки прав root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo "[ОШИБКА] Требуются права root для этого действия"
        echo "Используйте: sudo ./manage_service.sh"
        return 1
    fi
    return 0
}

# Функция показа статуса
show_status() {
    echo
    echo "========== СТАТУС СЛУЖБЫ =========="
    systemctl status "$SERVICE_NAME" --no-pager -l
    echo "==================================="
}

# Функция показа логов
show_logs() {
    echo
    echo "Выберите тип логов:"
    echo "  1. Последние 50 строк журнала systemd"
    echo "  2. Следить за логами в реальном времени"
    echo "  3. Логи ошибок приложения"
    echo "  4. Все логи за сегодня"
    echo
    read -p "Введите номер: " log_choice
    
    case $log_choice in
        1)
            echo
            echo "========== ПОСЛЕДНИЕ ЛОГИ =========="
            journalctl -u "$SERVICE_NAME" -n 50 --no-pager
            ;;
        2)
            echo
            echo "========== ЛОГИ В РЕАЛЬНОМ ВРЕМЕНИ =========="
            echo "Нажмите Ctrl+C для выхода"
            journalctl -u "$SERVICE_NAME" -f
            ;;
        3)
            echo
            echo "========== ЛОГИ ОШИБОК ПРИЛОЖЕНИЯ =========="
            if [[ -d "$INSTALL_DIR/logs" ]]; then
                latest_log=$(find "$INSTALL_DIR/logs" -name "errors_*.log" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
                if [[ -n "$latest_log" ]]; then
                    echo "Файл: $latest_log"
                    echo "---"
                    tail -50 "$latest_log"
                else
                    echo "Лог файлы ошибок не найдены"
                fi
            else
                echo "Директория логов не найдена: $INSTALL_DIR/logs"
            fi
            ;;
        4)
            echo
            echo "========== ВСЕ ЛОГИ ЗА СЕГОДНЯ =========="
            journalctl -u "$SERVICE_NAME" --since today --no-pager
            ;;
        *)
            echo "Неверный выбор"
            ;;
    esac
}

# Главное меню
while true; do
    echo
    echo "Выберите действие:"
    echo "  1. Показать статус службы"
    echo "  2. Запустить службу"
    echo "  3. Остановить службу" 
    echo "  4. Перезапустить службу"
    echo "  5. Показать логи"
    echo "  6. Включить автозагрузку"
    echo "  7. Отключить автозагрузку"
    echo "  8. Редактировать конфигурацию"
    echo "  9. Проверить конфигурацию"
    echo "  0. Выход"
    echo
    read -p "Введите номер действия: " choice
    
    case $choice in
        1)
            show_status
            ;;
        2)
            if check_root; then
                echo "Запуск службы $SERVICE_NAME..."
                systemctl start "$SERVICE_NAME"
                if systemctl is-active --quiet "$SERVICE_NAME"; then
                    echo "[OK] Служба запущена успешно"
                else
                    echo "[ОШИБКА] Не удалось запустить службу"
                fi
            fi
            ;;
        3)
            if check_root; then
                echo "Остановка службы $SERVICE_NAME..."
                systemctl stop "$SERVICE_NAME"
                echo "[OK] Служба остановлена"
            fi
            ;;
        4)
            if check_root; then
                echo "Перезапуск службы $SERVICE_NAME..."
                systemctl restart "$SERVICE_NAME"
                if systemctl is-active --quiet "$SERVICE_NAME"; then
                    echo "[OK] Служба перезапущена успешно"
                else
                    echo "[ОШИБКА] Не удалось перезапустить службу"
                fi
            fi
            ;;
        5)
            show_logs
            ;;
        6)
            if check_root; then
                echo "Включение автозагрузки..."
                systemctl enable "$SERVICE_NAME"
                echo "[OK] Автозагрузка включена"
            fi
            ;;
        7)
            if check_root; then
                echo "Отключение автозагрузки..."
                systemctl disable "$SERVICE_NAME"
                echo "[OK] Автозагрузка отключена"
            fi
            ;;
        8)
            if [[ -f "$INSTALL_DIR/.env" ]]; then
                echo "Редактирование $INSTALL_DIR/.env..."
                if command -v nano &> /dev/null; then
                    nano "$INSTALL_DIR/.env"
                elif command -v vi &> /dev/null; then
                    vi "$INSTALL_DIR/.env"
                else
                    echo "Редактор не найден. Установите nano или vi"
                fi
                echo "После изменения конфигурации перезапустите службу"
            else
                echo "Файл конфигурации не найден: $INSTALL_DIR/.env"
            fi
            ;;
        9)
            echo "Проверка конфигурации..."
            echo
            if [[ -f "$INSTALL_DIR/.env" ]]; then
                echo "=== Файл конфигурации ==="
                echo "Файл: $INSTALL_DIR/.env"
                echo
                grep -v '^#' "$INSTALL_DIR/.env" | grep -v '^$' | while IFS= read -r line; do
                    if [[ $line == *"TOKEN"* ]] || [[ $line == *"KEY"* ]]; then
                        var_name=$(echo "$line" | cut -d= -f1)
                        echo "$var_name=***скрыто***"
                    else
                        echo "$line"
                    fi
                done
            else
                echo "[ОШИБКА] Файл .env не найден"
            fi
            echo
            echo "=== Статус Python зависимостей ==="
            cd "$INSTALL_DIR" 2>/dev/null && python3 -c "
import sys
try:
    import aiogram, motor, pymongo, openai
    print('[OK] Все основные зависимости найдены')
except ImportError as e:
    print(f'[ОШИБКА] Отсутствует зависимость: {e}')
" || echo "[ОШИБКА] Не удалось проверить зависимости"
            ;;
        0)
            echo "До свидания!"
            exit 0
            ;;
        *)
            echo "[ОШИБКА] Неверный выбор"
            ;;
    esac
done 