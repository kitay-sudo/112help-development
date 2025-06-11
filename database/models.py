from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

class Database:
    client = None
    db = None

    @classmethod
    async def connect_to_mongo(cls):
        """Подключение к MongoDB"""
        cls.client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
        cls.db = cls.client.emergency_bot
        print("✅ Подключение к MongoDB установлено")

    @classmethod
    async def close_mongo_connection(cls):
        """Закрытие подключения к MongoDB"""
        if cls.client:
            cls.client.close()
            print("❌ Подключение к MongoDB закрыто")

class User:
    def __init__(self, user_id: int, username: str = None, first_name: str = None, 
                 last_name: str = None, is_blocked: bool = False):
        self.user_id = user_id
        self.username = username
        self.first_name = first_name
        self.last_name = last_name
        self.registration_date = datetime.now()
        self.is_blocked = is_blocked
        self.last_activity = datetime.now()
        self.command_count = 0
        self.warnings_count = 0

    def to_dict(self):
        """Преобразование в словарь для MongoDB"""
        return {
            "_id": self.user_id,
            "user_id": self.user_id,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "registration_date": self.registration_date,
            "is_blocked": self.is_blocked,
            "last_activity": self.last_activity,
            "command_count": self.command_count,
            "warnings_count": self.warnings_count
        }

    @classmethod
    async def create_user(cls, user_id: int, username: str = None, 
                         first_name: str = None, last_name: str = None):
        """Создание нового пользователя в базе данных"""
        user = cls(user_id, username, first_name, last_name)
        try:
            await Database.db.users.insert_one(user.to_dict())
            return user
        except Exception as e:
            print(f"❌ Ошибка создания пользователя: {e}")
            return None

    @classmethod
    async def get_user(cls, user_id: int):
        """Получение пользователя из базы данных"""
        try:
            user_data = await Database.db.users.find_one({"user_id": user_id})
            if user_data:
                user = cls(
                    user_data["user_id"],
                    user_data.get("username"),
                    user_data.get("first_name"),
                    user_data.get("last_name"),
                    user_data.get("is_blocked", False)
                )
                user.registration_date = user_data.get("registration_date", datetime.now())
                user.last_activity = user_data.get("last_activity", datetime.now())
                user.command_count = user_data.get("command_count", 0)
                user.warnings_count = user_data.get("warnings_count", 0)
                return user
            return None
        except Exception as e:
            print(f"❌ Ошибка получения пользователя: {e}")
            return None

    @classmethod
    async def get_or_create_user(cls, user_id: int, username: str = None, 
                                first_name: str = None, last_name: str = None):
        """Получение пользователя или создание нового"""
        user = await cls.get_user(user_id)
        if not user:
            user = await cls.create_user(user_id, username, first_name, last_name)
        return user

    async def update_activity(self):
        """Обновление активности пользователя"""
        try:
            await Database.db.users.update_one(
                {"user_id": self.user_id},
                {
                    "$set": {"last_activity": datetime.now()},
                    "$inc": {"command_count": 1}
                }
            )
            self.last_activity = datetime.now()
            self.command_count += 1
        except Exception as e:
            print(f"❌ Ошибка обновления активности: {e}")

    async def block_user(self, reason: str = "Нарушение правил"):
        """Блокировка пользователя"""
        try:
            await Database.db.users.update_one(
                {"user_id": self.user_id},
                {
                    "$set": {
                        "is_blocked": True,
                        "block_reason": reason,
                        "block_date": datetime.now()
                    }
                }
            )
            self.is_blocked = True
        except Exception as e:
            print(f"❌ Ошибка блокировки пользователя: {e}")

    async def unblock_user(self):
        """Разблокировка пользователя"""
        try:
            await Database.db.users.update_one(
                {"user_id": self.user_id},
                {
                    "$set": {"is_blocked": False},
                    "$unset": {"block_reason": "", "block_date": ""}
                }
            )
            self.is_blocked = False
        except Exception as e:
            print(f"❌ Ошибка разблокировки пользователя: {e}")

    async def add_warning(self):
        """Добавление предупреждения пользователю"""
        try:
            await Database.db.users.update_one(
                {"user_id": self.user_id},
                {"$inc": {"warnings_count": 1}}
            )
            self.warnings_count += 1
        except Exception as e:
            print(f"❌ Ошибка добавления предупреждения: {e}")



class CommandLog:
    """Модель для логирования команд"""
    
    @staticmethod
    async def log_command(user_id: int, command: str, success: bool = True, error: str = None):
        """Логирование выполненной команды"""
        try:
            log_entry = {
                "user_id": user_id,
                "command": command,
                "timestamp": datetime.now(),
                "success": success,
                "error": error
            }
            await Database.db.command_logs.insert_one(log_entry)
        except Exception as e:
            print(f"❌ Ошибка логирования команды: {e}")

 