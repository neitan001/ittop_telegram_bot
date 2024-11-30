import requests
import json
from datetime import datetime, timedelta
import pytz  # Для работы с часовыми поясами
import logging
from config import SCHEDULE_URL, USER_AGENT, ORIGIN, REFERER

USER_DATA_FILE = "users.json"
MOSCOW_TZ = pytz.timezone("Europe/Moscow")  # Московский часовой пояс

class MoscowTimeFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        # Получаем время с московским часовым поясом
        tz_aware_time = datetime.fromtimestamp(record.created, tz=MOSCOW_TZ)
        return tz_aware_time.strftime(datefmt or self.default_time_format)

def get_user_token(user_id):
    try:
        with open('users.json', 'r') as f:
            tokens = json.load(f)

        # Проверяем, что пользователь существует и у него есть токен
        user_data = tokens.get(str(user_id))
        if user_data and 'token' in user_data:
            return user_data['token']  # Возвращаем токен
        else:
            return None  # Возвращаем None, если токен не найден
        
    except FileNotFoundError:
        print("Файл users.json не найден.")
        return None
    except json.JSONDecodeError:
        print("Ошибка при декодировании JSON.")
        return None
    except Exception as e:
        print(f"Произошла ошибка: {e}")
        return None

def remove_user_token(user_id):
    username = get_username(user_id)
    try:
        with open('users.json', 'r') as f:
            tokens = json.load(f)
        
        # Проверяем, существует ли пользователь
        if str(user_id) in tokens:
            # Обнуляем токен для пользователя
            tokens[str(user_id)]["token"] = ""
            # Перезаписываем файл с обновлёнными токенами
            with open('users.json', 'w') as f:
                json.dump(tokens, f, indent=4)
            logger.info(f"Токен для пользователя {username} обнулён.")
        else:
            logger.warning(f"Токен для пользователя {username} не найден.")
    except FileNotFoundError:
        logger.error("Файл токенов не найден.")
    except KeyError:
        logger.error(f"Ошибка структуры данных для пользователя {username}.")

def get_username(user_id):
    """
    Получение имени пользователя (username) по user_id из файла users.json.
    """
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as file:
            user_data = json.load(file)
        return user_data.get(str(user_id), {}).get("username", f"User_{user_id}")
    except FileNotFoundError:
        logger.error(f"Файл {USER_DATA_FILE} не найден.")
        return f"User_{user_id}"

# Настройка логирования
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Создаем консольный обработчик с цветным выводом
console_handler = logging.StreamHandler()
console_handler.setFormatter(MoscowTimeFormatter(LOG_FORMAT, DATE_FORMAT))

# Устанавливаем уровень логирования и добавляем обработчик
logging.basicConfig(level=logging.INFO, handlers=[console_handler])
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Создание логгера
logger = logging.getLogger(__name__)

def get_headers(user_id):
    username = get_username(user_id)
    logger.debug(f"Получение заголовков для пользователя {username}.")
    user_data = load_user_data()
    token = user_data.get(str(user_id), {}).get("token")
    if token is None:
        logger.error(f"Токен пользователя {username} не найден.")
        raise ValueError("Токен пользователя не найден.")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": ORIGIN,
        "Referer": REFERER,
    }
    logger.debug(f"Заголовки для пользователя {username} успешно получены.")
    return headers

def load_user_data():
    try:
        logger.info("Загрузка данных пользователя из файла.")
        with open(USER_DATA_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            logger.info("Данные пользователя успешно загружены.")
            return data
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Ошибка при загрузке данных: {e}")
        return {}

def fetch_schedule(date, user_id):
    from bot import start
    from bot import handle_date_request
    username = get_username(user_id)
    logger.info(f"Запрос расписания для пользователя {username} на дату {date}.")
    url = SCHEDULE_URL.format(date)
    headers = get_headers(user_id)
    
    try:
        response = requests.get(url, headers=headers)
        
        # Если сервер вернул ошибку 401, логируем это, удаляем токен и выбрасываем исключение
        if response.status_code == 401:
            logger.error(f"Неавторизованный запрос для пользователя {username}. Токен может быть недействителен.")
            remove_user_token(user_id)  # Удаляем токен
            handle_date_request(update = Update, context = ContextTypes.DEFAULT_TYPE, invalid_token=True)
            raise ValueError("Токен недействителен или просрочен. Требуется повторная авторизация.")
        
        logger.info(f"Расписание для {username} на {date} успешно получено и передано пользователю\n")
        return response
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе расписания для {username} на {date}: {e}")
        return None


def format_schedule(schedule_info, date):
    # Проверка на выходной день
    day_of_week = datetime.strptime(date, "%Y-%m-%d").weekday()  # Получаем день недели
    if day_of_week == 5 or day_of_week == 6:  # Суббота (5) или Воскресенье (6)
        logger.info(f"День {date} - выходной.\n")
        return "Выходной день. Нет расписания."

    if not schedule_info:
        logger.warning("Не получено расписание, возможно, нет пар на этот день.")
        return "Нет пар на этот день."
    
    logger.debug("Форматирование расписания.")
    formatted_schedule = ""
    for entry in schedule_info:
        time_start = entry.get("started_at", "Неизвестно")
        time_end = entry.get("finished_at", "Неизвестно")
        subject = entry.get("subject_name", "Неизвестный предмет")
        room = entry.get("room_name", "Неизвестная аудитория")
        teacher = entry.get("teacher_name", "Неизвестный преподаватель")
        
        formatted_schedule += (
            f"🕒 {time_start} - {time_end} 🕒\n"
            f"📖 {subject}\n"
            f"🚪 {room}\n"
            f"👨‍🏫 {teacher}\n\n"
        )
    logger.debug("Расписание успешно отформатировано.")
    return formatted_schedule

def get_schedule(date, user_id):
    username = get_username(user_id)
    
    # Проверка формата даты
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        logger.error(f"Неверный формат даты для пользователя {username}: {date}. Используйте YYYY-MM-DD.")
        raise ValueError("Неверный формат даты. Используйте YYYY-MM-DD.")
    
    # Получаем расписание
    response = fetch_schedule(date, user_id)
    
    if response is None:
        # Если ответ пустой (None), то сообщаем об ошибке
        logger.error(f"Не удалось получить расписание для пользователя {username} на {date}.")
        raise ValueError(f"Не удалось получить расписание для {username} на {date}. Повторите попытку позже.")
    
    try:
        schedule_info = response.json()  # Преобразуем ответ в формат JSON
    except ValueError:
        logger.error(f"Ошибка при разборе ответа для пользователя {username} на {date}. Ответ не в формате JSON.")
        raise ValueError("Ошибка при разборе данных расписания. Ответ не в формате JSON.")
    
    return format_schedule(schedule_info, date)  # Форматируем расписание для отправки


def get_today_schedule(user_id):
    username = get_username(user_id)
    date = datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d")  # Московская дата
    logger.info(f"Получение расписания на сегодня для пользователя {username}.")
    return get_schedule(date, user_id)

def get_tomorrow_schedule(user_id):
    username = get_username(user_id)
    date = (datetime.now(MOSCOW_TZ) + timedelta(days=1)).strftime("%Y-%m-%d")  # Московская дата
    logger.info(f"Получение расписания на завтра для пользователя {username}.")
    return get_schedule(date, user_id)

def get_week_schedule(user_id):
    username = get_username(user_id)
    start_of_week = datetime.now(MOSCOW_TZ) - timedelta(days=datetime.now(MOSCOW_TZ).weekday())
    logger.info(f"Получение расписания на неделю для пользователя {username}.")
    week_schedule = ""
    for i in range(5):  # Понедельник - Пятница
        date = (start_of_week + timedelta(days=i)).strftime("%Y-%m-%d")
        day_name = get_day_name_in_russian((start_of_week + timedelta(days=i)).weekday())
        schedule_info = fetch_schedule(date, user_id).json()  # Получаем данные
        formatted_schedule = format_schedule(schedule_info) if schedule_info else "Нет пар"
        week_schedule += f"📅 {day_name} ({date}):\n{formatted_schedule}\n"
    logger.info(f"Расписание на неделю для пользователя {username} получено.")
    return week_schedule

def get_next_week_schedule(user_id):
    username = get_username(user_id)
    # Получаем дату начала следующей недели (понедельник)
    today = datetime.now(MOSCOW_TZ)
    days_until_next_monday = (7 - today.weekday()) % 7 + 7  # Количество дней до следующего понедельника
    start_of_next_week = today + timedelta(days=days_until_next_monday)
    
    logger.info(f"Получение расписания на следующую неделю для пользователя {username}.")
    next_week_schedule = ""
    
    for i in range(5):  # Понедельник - Пятница
        date = (start_of_next_week + timedelta(days=i)).strftime("%Y-%m-%d")
        day_name = get_day_name_in_russian((start_of_next_week + timedelta(days=i)).weekday())
        schedule_info = fetch_schedule(date, user_id).json()  # Получаем данные
        formatted_schedule = format_schedule(schedule_info, date) if schedule_info else "Нет пар"
        next_week_schedule += f"📅 {day_name} ({date}):\n{formatted_schedule}\n"
    
    logger.info(f"Расписание на следующую неделю для пользователя {username} получено.")
    return next_week_schedule

def get_day_name_in_russian(day_index):
    days_in_russian = {
        0: "Понедельник",
        1: "Вторник",
        2: "Среда",
        3: "Четверг",
        4: "Пятница",
        5: "Суббота",
        6: "Воскресенье",
    }
    return days_in_russian.get(day_index, "Неизвестный день")