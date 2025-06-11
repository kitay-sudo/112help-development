import logging
import sys
from datetime import datetime
import os
from pathlib import Path

class RussianFormatter(logging.Formatter):
    """Форматтер логов на русском языке"""
    
    def __init__(self):
        super().__init__()
        
    def format(self, record):
        # Форматирование времени на русском
        dt = datetime.fromtimestamp(record.created)
        time_str = dt.strftime("%d.%m.%Y %H:%M:%S")
        
        # Перевод уровней на русский
        level_translations = {
            'DEBUG': 'ОТЛАДКА',
            'INFO': 'ИНФО',
            'WARNING': 'ПРЕДУПРЕЖДЕНИЕ', 
            'ERROR': 'ОШИБКА',
            'CRITICAL': 'КРИТИЧЕСКАЯ'
        }
        
        level_ru = level_translations.get(record.levelname, record.levelname)
        
        # Основное сообщение
        message = f"[{time_str}] {level_ru} - {record.getMessage()}"
        
        # Добавляем traceback только для ошибок и только в файл
        if record.exc_info and hasattr(record, 'is_file_handler'):
            message += f"\n{self.formatException(record.exc_info)}"
            
        return message

class FileFormatter(RussianFormatter):
    """Специальный форматтер для файлов с traceback"""
    
    def format(self, record):
        record.is_file_handler = True
        return super().format(record)

def setup_logging():
    """Настройка системы логирования"""
    
    # Создаем директорию для логов
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Очищаем существующие обработчики
    root_logger.handlers.clear()
    
    # Консольный обработчик (только INFO и выше БЕЗ traceback)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = RussianFormatter()
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Файловый обработчик для ВСЕХ ошибок (ERROR и CRITICAL) С traceback
    error_file = log_dir / f"errors_{datetime.now().strftime('%Y%m%d')}.log"
    error_handler = logging.FileHandler(error_file, encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_formatter = FileFormatter()
    error_handler.setFormatter(error_formatter)
    root_logger.addHandler(error_handler)
    
    # Удаляем файловое логирование всех действий - оставляем только ошибки в файлах
    
    return root_logger

def log_exception(logger, message: str, exception: Exception = None):
    """Удобная функция для логирования исключений"""
    if exception:
        logger.error(f"{message}: {str(exception)}", exc_info=True)
    else:
        logger.error(message, exc_info=True)

def log_user_action(logger, user_id: int, action: str, success: bool = True, details: str = None):
    """Логирование действий пользователей"""
    status = "успешно" if success else "с ошибкой"
    message = f"Пользователь {user_id} выполнил действие '{action}' {status}"
    if details:
        message += f" - {details}"
    
    if success:
        logger.info(message)
    else:
        logger.warning(message)

def log_command_execution(logger, user_id: int, command: str, execution_time: float = None):
    """Логирование выполнения команд"""
    message = f"Пользователь {user_id} выполнил команду '{command}'"
    if execution_time:
        message += f" за {execution_time:.3f}с"
    logger.info(message)

def log_system_event(logger, event: str, details: str = None):
    """Логирование системных событий"""
    message = f"Системное событие: {event}"
    if details:
        message += f" - {details}"
    logger.info(message)

def log_security_event(logger, user_id: int, event: str, severity: str = "warning"):
    """Логирование событий безопасности"""
    message = f"БЕЗОПАСНОСТЬ: Пользователь {user_id} - {event}"
    
    if severity == "critical":
        logger.critical(message)
    elif severity == "error":
        logger.error(message)
    else:
        logger.warning(message)

# Создаем глобальный логгер для удобства
app_logger = None

def get_logger():
    """Получение настроенного логгера"""
    global app_logger
    if app_logger is None:
        app_logger = setup_logging()
    return app_logger

# Алиасы для удобства
def log_info(message: str):
    get_logger().info(message)

def log_warning(message: str):
    get_logger().warning(message)

def log_error(message: str, exception: Exception = None):
    if exception:
        get_logger().error(f"{message}: {str(exception)}", exc_info=True)
    else:
        get_logger().error(message)

def log_critical(message: str, exception: Exception = None):
    if exception:
        get_logger().critical(f"{message}: {str(exception)}", exc_info=True)
    else:
        get_logger().critical(message) 