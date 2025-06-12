# 🐧 Установка 112help как Ubuntu служба

Инструкции по установке и управлению Telegram-ботом 112help в качестве системной службы Ubuntu с использованием systemd.

## 📋 Требования

- **Ubuntu 18.04+** или другие Linux дистрибутивы с systemd
- **Права sudo/root** для установки службы
- **Python 3.8+** и pip3
- **Настроенный .env файл** с токеном бота

## 🚀 Установка службы

### 1. Подготовка системы
```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Python и зависимостей
sudo apt install python3 python3-pip python3-venv -y

# Проверка версии Python
python3 --version
```

### 2. Подготовка проекта
```bash
# Скачайте проект в текущую директорию
# Убедитесь что файлы main.py, requirements.txt и .env присутствуют

# Проверка работы бота
python3 -m pip install -r requirements.txt
python3 main.py  # Ctrl+C для остановки после проверки
```

### 3. Установка службы
```bash
# Сделайте скрипт исполняемым
chmod +x install_service.sh

# Запустите установку (требуются права root)
sudo ./install_service.sh
```

### 4. Настройка конфигурации
```bash
# Отредактируйте конфигурацию (обязательно!)
sudo nano /opt/112help/.env

# Минимальные настройки:
# BOT_TOKEN=ваш_токен_бота
# ADMIN_IDS=ваш_telegram_id
```

### 5. Запуск службы
```bash
# Запуск службы
sudo systemctl start 112help

# Проверка статуса
sudo systemctl status 112help

# Просмотр логов
sudo journalctl -u 112help -f
```

## 🎛️ Управление службой

### Основные команды systemctl
```bash
# Статус службы
sudo systemctl status 112help

# Запуск
sudo systemctl start 112help

# Остановка
sudo systemctl stop 112help

# Перезапуск
sudo systemctl restart 112help

# Автозагрузка
sudo systemctl enable 112help   # Включить
sudo systemctl disable 112help  # Отключить

# Просмотр логов
sudo journalctl -u 112help      # Все логи
sudo journalctl -u 112help -f   # Слежение в реальном времени
sudo journalctl -u 112help -n 50 # Последние 50 строк
```

### Интерактивное управление
```bash
# Запуск интерактивного меню
./manage_service.sh

# Доступные действия:
# 1. Показать статус службы
# 2. Запустить службу  
# 3. Остановить службу
# 4. Перезапустить службу
# 5. Показать логи
# 6. Включить автозагрузку
# 7. Отключить автозагрузку
# 8. Редактировать конфигурацию
# 9. Проверить конфигурацию
```

## 🗑️ Удаление службы

```bash
# Сделайте скрипт исполняемым
chmod +x uninstall_service.sh

# Запустите удаление
sudo ./uninstall_service.sh

# Скрипт предложит:
# - Удалить файлы приложения (/opt/112help)
# - Удалить пользователя службы
```

## 📊 Мониторинг и логи

### Системные логи (systemd journal)
```bash
# Все логи службы
sudo journalctl -u 112help

# Логи с определенного времени
sudo journalctl -u 112help --since "2024-01-01 00:00:00"
sudo journalctl -u 112help --since today
sudo journalctl -u 112help --since "1 hour ago"

# Логи в реальном времени
sudo journalctl -u 112help -f

# Последние N строк
sudo journalctl -u 112help -n 100

# Логи с приоритетом ошибок
sudo journalctl -u 112help -p err
```

### Логи приложения
```bash
# Директория логов приложения
ls -la /opt/112help/logs/

# Просмотр логов ошибок
sudo tail -f /opt/112help/logs/errors_$(date +%Y%m%d).log

# Все лог файлы
sudo find /opt/112help/logs -name "*.log" -type f
```

## ⚙️ Конфигурация службы

### Основные параметры
Файл службы: `/etc/systemd/system/112help.service`

```ini
[Unit]
Description=112help - Помощник экстренных служб
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=112help
Group=112help
WorkingDirectory=/opt/112help
ExecStart=/usr/bin/python3 /opt/112help/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Изменение конфигурации службы
```bash
# Редактирование файла службы
sudo systemctl edit 112help --full

# После изменений
sudo systemctl daemon-reload
sudo systemctl restart 112help
```

### Переменные окружения
Файл конфигурации: `/opt/112help/.env`

```bash
# Обязательные настройки
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=123456789,987654321

# Опциональные настройки
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=emergency_bot
OPENAI_API_KEY=your_openai_key
LOG_LEVEL=INFO
ENVIRONMENT=production
```

## 🔧 Настройка безопасности

### Права доступа
```bash
# Служба работает под пользователем 112help
sudo ls -la /opt/112help  # Проверка владельца файлов

# Изменение прав при необходимости
sudo chown -R 112help:112help /opt/112help
sudo chmod 755 /opt/112help
sudo chmod 644 /opt/112help/.env
```

### Ограничения systemd
Служба настроена с ограничениями безопасности:
- `NoNewPrivileges=yes` - запрет повышения привилегий
- `PrivateTmp=yes` - изолированная временная директория
- `ProtectSystem=strict` - защита системных директорий
- `ProtectHome=yes` - защита домашних директорий

## 🚨 Устранение неисправностей

### Служба не запускается
```bash
# 1. Проверьте статус службы
sudo systemctl status 112help

# 2. Проверьте логи
sudo journalctl -u 112help -n 50

# 3. Проверьте конфигурацию
sudo /opt/112help/main.py  # Ручной запуск для проверки

# 4. Проверьте права доступа
sudo ls -la /opt/112help
```

### Проблемы с Python зависимостями
```bash
# Переустановка зависимостей
cd /opt/112help
sudo -u 112help python3 -m pip install -r requirements.txt

# Проверка импортов
sudo -u 112help python3 -c "import aiogram, motor, pymongo; print('OK')"
```

### Проблемы с токеном/конфигурацией
```bash
# Проверка .env файла
sudo cat /opt/112help/.env

# Тест токена бота
sudo -u 112help python3 -c "
import os
from dotenv import load_dotenv
load_dotenv('/opt/112help/.env')
print('BOT_TOKEN найден:', bool(os.getenv('BOT_TOKEN')))
"
```

### Переустановка службы
```bash
# Полная переустановка
sudo ./uninstall_service.sh  # Удаление
sudo ./install_service.sh    # Установка заново
```

## 📁 Структура файлов

```
/opt/112help/                 # Директория приложения
├── main.py                   # Основной скрипт
├── requirements.txt          # Python зависимости
├── .env                      # Конфигурация
├── data/                     # Данные приложения
├── database/                 # Модели БД
├── utils/                    # Утилиты
└── logs/                     # Логи приложения
    └── errors_YYYYMMDD.log

/etc/systemd/system/
└── 112help.service          # Файл службы systemd

Домашняя директория проекта:
├── 112help.service          # Шаблон службы
├── install_service.sh       # Установка
├── uninstall_service.sh     # Удаление  
├── manage_service.sh        # Управление
└── SERVICE_README.md        # Документация
```

## 📋 Контрольный список

### Перед установкой:
- [ ] Ubuntu 18.04+ с systemd
- [ ] Python 3.8+ установлен
- [ ] pip3 установлен
- [ ] Проект скачан и распакован
- [ ] main.py и requirements.txt присутствуют
- [ ] Токен бота получен
- [ ] Права sudo доступны

### После установки:
- [ ] Службы создана: `systemctl status 112help`
- [ ] Автозагрузка включена: `systemctl is-enabled 112help`
- [ ] Служба запущена: `systemctl is-active 112help`
- [ ] Конфигурация настроена: `/opt/112help/.env`
- [ ] Бот отвечает в Telegram
- [ ] Логи работают: `journalctl -u 112help`

## 🔗 Полезные команды

```bash
# Быстрая диагностика
sudo systemctl status 112help && sudo journalctl -u 112help -n 10

# Мониторинг ресурсов
sudo systemctl show 112help --property=MainPID
top -p $(sudo systemctl show 112help --property=MainPID --value)

# Экспорт логов
sudo journalctl -u 112help --since today > 112help_logs_$(date +%Y%m%d).log

# Проверка автозагрузки
systemctl list-unit-files | grep 112help
```

---

**Разработчик**: @kitay9  
**Поддержка**: Telegram @kitay9  
**Версия**: 2.0  
**Совместимость**: Ubuntu 18.04+, Debian 10+, CentOS 8+ 