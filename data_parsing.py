import requests
import json
import os
import logging
from config import USER_AGENT, AUTH_URL, ORIGIN, REFERER, APPLICATION_KEY

# Путь к файлу, где будут храниться данные пользователей
USER_DATA_FILE = "users.json"

# Настройка логирования
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Создаем консольный обработчик с цветным выводом

class MoscowTimeFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        # Получаем время с московским часовым поясом
        tz_aware_time = datetime.fromtimestamp(record.created, tz=MOSCOW_TZ)
        return tz_aware_time.strftime(datefmt or self.default_time_format)

console_handler = logging.StreamHandler()
console_handler.setFormatter(MoscowTimeFormatter(LOG_FORMAT, DATE_FORMAT))

# Устанавливаем уровень логирования и добавляем обработчик
logging.basicConfig(level=logging.INFO, handlers=[console_handler])
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Создание логгера
logger = logging.getLogger(__name__)

# URL для авторизации
AUTH_URL = "https://msapi.top-academy.ru/api/v2/auth/login"

# Функция для загрузки данных пользователей из JSON файла
def load_user_data():
    # Проверка на существование файла и его валидность
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r", encoding="utf-8") as file:
                logger.info(f"Данные пользователей успешно загружены из файла {USER_DATA_FILE}.")
                return json.load(file)
        except json.JSONDecodeError:
            logger.error(f"Файл {USER_DATA_FILE} повреждён. Создаём новый файл.")
            return {}
    else:
        logger.info(f"Файл {USER_DATA_FILE} не найден. Создаём новый файл.")
        return {}

# Функция для сохранения данных пользователей в JSON файл
def save_user_data(user_data):
    try:
        with open(USER_DATA_FILE, "w", encoding="utf-8") as file:
            json.dump(user_data, file, ensure_ascii=False, indent=4)
        logger.info(f"Данные пользователей успешно сохранены в файл {USER_DATA_FILE}.")
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных в файл {USER_DATA_FILE}: {e}")

# Функция для авторизации и получения JWT токена
def authenticate_user(username, password, application_key):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": ORIGIN,
        "Referer": REFERER
    }

    # Тело запроса с логином, паролем и application_key
    data = {
        "username": username,
        "password": password,
        "application_key": application_key
    }

    try:
        # Отправляем POST-запрос на сервер для авторизации
        logger.debug(f"Попытка авторизации для пользователя: {username}")
        response = requests.post(AUTH_URL, headers=headers, json=data)

        if response.status_code == 200:
            # Ответ в формате JSON
            response_data = response.json()

            # Проверяем, есть ли JWT токен в ответе
            if 'access_token' in response_data:
                jwt_token = response_data['access_token']
                logger.info(f"Авторизация успешна для пользователя")
                return jwt_token
            else:
                logger.warning(f"Не удалось получить токен для пользователя. Ответ сервера: {response_data}")
                return None
        else:
            logger.error(f"Ошибка авторизации для пользователя. Статус: {response.status_code}")
            logger.error(f"Ответ от сервера: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Произошла ошибка при авторизации пользователя: {e}")
        return None

# Функция для получения токена пользователя из JSON
def get_user_token(username):
    user_data = load_user_data()
    for user in user_data.values():
        if user["username"] == username:
            logger.debug(f"Токен для пользователя {username} найден.")
            return user.get("token")
    logger.warning(f"Токен для пользователя {username} не найден.")
    return None

# Функция для сохранения токена пользователя в JSON
def save_user_token(username, token):
    user_data = load_user_data()

    # Если пользователя нет в данных, добавляем нового
    if username not in user_data:
        user_data[username] = {"username": username, "token": token}
        logger.info(f"Новый токен для пользователя {username} сохранён.")
    else:
        # Если пользователь уже есть, обновляем его токен
        user_data[username]["token"] = token
        logger.info(f"Токен для пользователя {username} обновлён.")

    # Сохраняем данные обратно в файл
    save_user_data(user_data)
