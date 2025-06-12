from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
import os
import json
from dotenv import load_dotenv

load_dotenv()

class Database:
    client = None
    db = None
    connected = False
    # Настройки хранения
    use_mongodb = os.getenv("USE_MONGODB", "false").lower() == "true"
    local_storage_file = "local_users.json"
    text_storage_file = "users.txt"
    
    @classmethod
    def _load_text_storage(cls):
        """Загрузка пользователей из текстового файла"""
        users = {}
        try:
            if os.path.exists(cls.text_storage_file):
                with open(cls.text_storage_file, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if line and '|' in line:
                            try:
                                parts = line.split('|')
                                if len(parts) >= 6:
                                    user_id = parts[0]
                                    username = parts[1] if parts[1] != 'None' else None
                                    first_name = parts[2] if parts[2] != 'None' else None
                                    last_name = parts[3] if parts[3] != 'None' else None
                                    reg_date = datetime.fromisoformat(parts[4])
                                    last_activity = datetime.fromisoformat(parts[5])
                                    command_count = int(parts[6]) if len(parts) > 6 else 0
                                    is_blocked = parts[7].lower() == 'true' if len(parts) > 7 else False
                                    
                                    users[user_id] = {
                                        'user_id': int(user_id),
                                        'username': username,
                                        'first_name': first_name,
                                        'last_name': last_name,
                                        'registration_date': reg_date,
                                        'last_activity': last_activity,
                                        'command_count': command_count,
                                        'is_blocked': is_blocked
                                    }
                            except (ValueError, IndexError) as e:
                                print(f"⚠️ Ошибка парсинга строки {line_num}: {e}")
        except Exception as e:
            print(f"❌ Ошибка загрузки текстового хранилища: {e}")
        return users
    
    @classmethod
    def _save_text_storage(cls, users):
        """Сохранение пользователей в текстовый файл"""
        try:
            with open(cls.text_storage_file, 'w', encoding='utf-8') as f:
                for user_data in users.values():
                    line = f"{user_data['user_id']}|{user_data.get('username', 'None')}|{user_data.get('first_name', 'None')}|{user_data.get('last_name', 'None')}|{user_data['registration_date'].isoformat()}|{user_data['last_activity'].isoformat()}|{user_data.get('command_count', 0)}|{user_data.get('is_blocked', False)}\n"
                    f.write(line)
        except Exception as e:
            print(f"❌ Ошибка сохранения текстового хранилища: {e}")

    @classmethod
    def _load_local_storage(cls):
        """Загрузка локального хранилища из файла"""
        try:
            if os.path.exists(cls.local_storage_file):
                with open(cls.local_storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Конвертируем строки обратно в datetime объекты
                    for user_id, user_data in data.items():
                        if 'registration_date' in user_data and isinstance(user_data['registration_date'], str):
                            user_data['registration_date'] = datetime.fromisoformat(user_data['registration_date'])
                        if 'last_activity' in user_data and isinstance(user_data['last_activity'], str):
                            user_data['last_activity'] = datetime.fromisoformat(user_data['last_activity'])
                    return data
        except Exception as e:
            print(f"❌ Ошибка загрузки локального хранилища: {e}")
        return {}
    
    @classmethod
    def _save_local_storage(cls, data):
        """Сохранение локального хранилища в файл"""
        try:
            # Конвертируем datetime объекты в строки для JSON
            json_data = {}
            for user_id, user_data in data.items():
                json_user_data = user_data.copy()
                if 'registration_date' in json_user_data and isinstance(json_user_data['registration_date'], datetime):
                    json_user_data['registration_date'] = json_user_data['registration_date'].isoformat()
                if 'last_activity' in json_user_data and isinstance(json_user_data['last_activity'], datetime):
                    json_user_data['last_activity'] = json_user_data['last_activity'].isoformat()
                json_data[user_id] = json_user_data
            
            with open(cls.local_storage_file, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Ошибка сохранения локального хранилища: {e}")

    @classmethod
    async def connect_to_mongo(cls):
        """Подключение к MongoDB или настройка локального хранилища"""
        try:
            # Проверяем настройку USE_MONGODB
            if not cls.use_mongodb:
                print("📂 Используется локальное хранилище (USE_MONGODB=false)")
                print(f"📄 Пользователи сохраняются в {cls.text_storage_file}")
                cls.connected = False
                return
            
            mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
            database_name = os.getenv("DATABASE_NAME", "emergency_bot")
            
            # Проверяем, не отключена ли БД для тестирования
            if mongodb_url.lower() == "disabled":
                print("⚠️  База данных отключена (MONGODB_URL=disabled)")
                print(f"📄 Переключение на текстовое хранилище: {cls.text_storage_file}")
                cls.connected = False
                return
            
            cls.client = AsyncIOMotorClient(mongodb_url, serverSelectionTimeoutMS=5000)
            # Проверяем подключение
            await cls.client.admin.command('ping')
            cls.db = cls.client[database_name]
            cls.connected = True
            print(f"✅ Подключение к MongoDB установлено: {mongodb_url}")
            print(f"✅ Используется база данных: {database_name}")
            
        except Exception as e:
            print(f"❌ Ошибка подключения к MongoDB: {e}")
            print(f"📄 Переключение на текстовое хранилище: {cls.text_storage_file}")
            cls.connected = False

    @classmethod
    async def connect(cls):
        """Алиас для connect_to_mongo() для совместимости"""
        await cls.connect_to_mongo()

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
            if Database.connected and Database.use_mongodb:
                await Database.db.users.insert_one(user.to_dict())
            elif Database.use_mongodb:
                # Сохранение в JSON когда MongoDB включено но недоступно
                local_data = Database._load_local_storage()
                local_data[str(user_id)] = user.to_dict()
                Database._save_local_storage(local_data)
            else:
                # Сохранение в текстовый файл
                users = Database._load_text_storage()
                users[str(user_id)] = user.to_dict()
                Database._save_text_storage(users)
            return user
        except Exception as e:
            print(f"❌ Ошибка создания пользователя: {e}")
            return None

    @classmethod
    async def get_user(cls, user_id: int):
        """Получение пользователя из базы данных"""
        try:
            if Database.connected and Database.use_mongodb:
                user_data = await Database.db.users.find_one({"user_id": user_id})
            elif Database.use_mongodb:
                # Получение из JSON хранилища
                local_data = Database._load_local_storage()
                user_data = local_data.get(str(user_id))
            else:
                # Получение из текстового файла
                users = Database._load_text_storage()
                user_data = users.get(str(user_id))
            
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
            self.last_activity = datetime.now()
            self.command_count += 1
            
            if Database.connected and Database.use_mongodb:
                await Database.db.users.update_one(
                    {"user_id": self.user_id},
                    {
                        "$set": {"last_activity": self.last_activity},
                        "$inc": {"command_count": 1}
                    }
                )
            elif Database.use_mongodb:
                # Обновление в JSON хранилище
                local_data = Database._load_local_storage()
                if str(self.user_id) in local_data:
                    local_data[str(self.user_id)]["last_activity"] = self.last_activity
                    local_data[str(self.user_id)]["command_count"] = self.command_count
                    Database._save_local_storage(local_data)
            else:
                # Обновление в текстовом файле
                users = Database._load_text_storage()
                if str(self.user_id) in users:
                    users[str(self.user_id)]["last_activity"] = self.last_activity
                    users[str(self.user_id)]["command_count"] = self.command_count
                    Database._save_text_storage(users)
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

    @staticmethod
    async def get_user_stats():
        """Получение статистики пользователей для админов"""
        try:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            week_ago = today - timedelta(days=7)
            
            if Database.connected and Database.use_mongodb:
                # Статистика из MongoDB
                total_users = await Database.db.users.count_documents({})
                blocked_users = await Database.db.users.count_documents({"is_blocked": True})
                active_today = await Database.db.users.count_documents({
                    "last_activity": {"$gte": today}
                })
                active_week = await Database.db.users.count_documents({
                    "last_activity": {"$gte": week_ago}
                })
                new_today = await Database.db.users.count_documents({
                    "registration_date": {"$gte": today}
                })
                storage_type = "mongodb"
            elif Database.use_mongodb:
                # Статистика из JSON хранилища (когда MongoDB включено но недоступно)
                local_data = Database._load_local_storage()
                total_users = len(local_data)
                blocked_users = 0
                active_today = 0
                active_week = 0
                new_today = 0
                
                for user_data in local_data.values():
                    if user_data.get("is_blocked", False):
                        blocked_users += 1
                    
                    last_activity = user_data.get("last_activity")
                    if isinstance(last_activity, datetime) and last_activity >= today:
                        active_today += 1
                    if isinstance(last_activity, datetime) and last_activity >= week_ago:
                        active_week += 1
                    
                    registration_date = user_data.get("registration_date")
                    if isinstance(registration_date, datetime) and registration_date >= today:
                        new_today += 1
                storage_type = "json_backup"
            else:
                # Статистика из текстового файла
                users = Database._load_text_storage()
                total_users = len(users)
                blocked_users = 0
                active_today = 0
                active_week = 0
                new_today = 0
                
                for user_data in users.values():
                    if user_data.get("is_blocked", False):
                        blocked_users += 1
                    
                    last_activity = user_data.get("last_activity")
                    if isinstance(last_activity, datetime) and last_activity >= today:
                        active_today += 1
                    if isinstance(last_activity, datetime) and last_activity >= week_ago:
                        active_week += 1
                    
                    registration_date = user_data.get("registration_date")
                    if isinstance(registration_date, datetime) and registration_date >= today:
                        new_today += 1
                storage_type = "text_file"
            
            return {
                "total": total_users,
                "blocked": blocked_users,
                "active_today": active_today,
                "active_week": active_week,
                "new_today": new_today,
                "storage_type": storage_type
            }
        except Exception as e:
            print(f"❌ Ошибка получения статистики: {e}")
            return {"total": 0, "blocked": 0, "active_today": 0, "active_week": 0, "new_today": 0, "error": True}

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

 