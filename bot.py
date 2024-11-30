import logging
import time
from datetime import datetime
import json
import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, ConversationHandler, filters,
)
from datetime import datetime, timedelta
import pytz  # Для работы с часовыми поясами
from config import BOT_TOKEN, APPLICATION_KEY
from retrieve_schedule import get_schedule  # Импортируем функцию для получения расписания
from data_parsing import authenticate_user  # Функция для авторизации

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

# Шаги для ConversationHandler
LOGIN, PASSWORD = range(2)

# Московский часовой пояс
MOSCOW_TZ = pytz.timezone("Europe/Moscow")

# Функция для загрузки данных пользователей из JSON файла
def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r", encoding="utf-8") as file:
                return json.load(file)
        except json.JSONDecodeError:
            logger.error(f"Файл {USER_DATA_FILE} повреждён. Создаём новый файл.")
            return {}  # Возвращаем пустой словарь, если JSON невалиден
    else:
        # Если файл не существует, создаем новый
        logger.info(f"Файл {USER_DATA_FILE} не найден. Создаём новый файл.")
        return {}

# Функция для сохранения данных пользователей в JSON файл
def save_user_data(user_data):
    try:
        with open(USER_DATA_FILE, "w", encoding="utf-8") as file:
            json.dump(user_data, file, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных в файл: {e}")

# Функция для получения токена пользователя по user_id
def get_user_token(user_id):
    user_data = load_user_data()
    return user_data.get(str(user_id), {}).get("token")

# Функция для сохранения токена пользователя в JSON
def save_user_token(user_id, username, token):
    user_data = load_user_data()
    
    # Добавляем или обновляем информацию о пользователе
    user_data[str(user_id)] = {
        "username": username,
        "token": token
    }

    try:
        # Сохраняем обновленные данные в файл
        save_user_data(user_data)
        logger.info(f"Токен для пользователя {username} сохранен.")
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных: {e}")

# Переопределение индексов дней недели в более понятный формат на русский язык
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

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE, invalid_token=False):
    if update.message.chat.type != 'private':
        return  # Игнорируем команды, если они не в личном чате

    user_id = update.message.from_user.id
    token = get_user_token(user_id)  # Получение токена из файла

    logger.debug(f"Пользователь {user_id} вызвал команду /start.")
    
    if invalid_token:
        # Если токен недействителен, показываем сообщение и предлагаем авторизацию
        keyboard = [["Войти"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Ваш токен недействителен. Пожалуйста, авторизуйтесь заново, используя кнопку 'Войти'.",
            reply_markup=reply_markup,
        )
    elif token:
        # Если пользователь уже авторизован, показываем остальные кнопки
        keyboard = [["Сегодня", "Завтра"], ["Расписание на неделю"], ["Расписание на следующую неделю"], ["Выбрать дату"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Добро пожаловать! Вы уже авторизованы.\n\nВыберите действие:",
            reply_markup=reply_markup,
        )
    else:
        # Если пользователь не авторизован, показываем только кнопку "Войти"
        keyboard = [["Войти"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Привет! Я бот расписания для IT TOP Ryazan. Нажмите 'Войти' для авторизации.",
            reply_markup=reply_markup,
        )

# Команда /login
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверяем, что сообщение приходит из личного чата
    if update.message.chat.type != 'private':
        return  # Игнорируем команду, если это не личное сообщение

    logger.debug(f"Пользователь {update.message.from_user.id} начал процесс авторизации.")
    await update.message.reply_text("Введите ваш логин:")
    return LOGIN

# Получение логина
async def get_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["login"] = update.message.text
    logger.info(f"Пользователь {update.message.from_user.username} ввел логин.")
    await update.message.reply_text("Введите ваш пароль:")
    return PASSWORD

# Получение пароля и авторизация
async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text
    login = context.user_data["login"]
    user_id = update.message.from_user.id  # Получаем user_id

    # Авторизация
    application_key = APPLICATION_KEY  # Укажите свой application_key
    token = authenticate_user(login, password, application_key)  # Передаем только login, password, application_key

    if token:
        save_user_token(user_id, update.message.from_user.username, token)  # Сохраняем токен в файле
        await update.message.reply_text("Авторизация успешна! Теперь вы можете запрашивать расписание.")
        
        # После успешной авторизации показываем кнопки для расписания
        keyboard = [["Сегодня", "Завтра"], ["Расписание на неделю"], ["Расписание на следующую неделю"], ["Выбрать дату"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)
        
        return ConversationHandler.END
    else:
        await update.message.reply_text("Ошибка авторизации. Попробуйте снова.")
        return ConversationHandler.END

# Обработка текстовых сообщений (например, выбор расписания)
async def handle_date_request(update: Update, context: ContextTypes.DEFAULT_TYPE, invalid_token=False):
    if update.message.chat.type != 'private':
        return  # Игнорируем сообщения, если они не из личного чата

    user_id = update.message.from_user.id
    token = get_user_token(user_id)  # Получение токена из файла

    if invalid_token:
        # Если токен недействителен, показываем сообщение и предлагаем авторизацию
        keyboard = [["Войти"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Ваш токен недействителен. Пожалуйста, авторизуйтесь заново, используя кнопку 'Войти'.",
            reply_markup=reply_markup,
        )

    if not token:
        # Если токен не найден, показываем сообщение и предлагаем авторизацию
        keyboard = [["Войти"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Ваш токен недействителен. Пожалуйста, авторизуйтесь заново, используя кнопку 'Войти'.",
            reply_markup=reply_markup,
        )
        return

    text = update.message.text
    logger.info(f"Пользователь {update.message.from_user.username} ввёл: {text}")

    try:
        if text in ["Сегодня", "Завтра"]:
            today = datetime.now(MOSCOW_TZ)
            date = today.strftime("%Y-%m-%d") if text == "Сегодня" else (today + timedelta(days=1)).strftime("%Y-%m-%d")
            schedule_info = get_schedule(date, user_id)
            await update.message.reply_text(f"📆 {date} - Расписание:\n\n{schedule_info}")
        elif text == "Расписание на неделю":
            await show_week_schedule(update, token)
        elif text == "Расписание на следующую неделю":
            await get_next_week_schedule(update, context)
        elif text == "Выбрать дату":
            await update.message.reply_text("Введите дату в формате YYYY-MM-DD:")
        else:
            try:
                date = datetime.strptime(text, "%Y-%m-%d").strftime("%Y-%m-%d")
                schedule_info = get_schedule(date, user_id)
                await update.message.reply_text(f"📆 {date} - Расписание:\n\n{schedule_info}")
            except ValueError:
                pass
    except ValueError:
        pass

# Показать расписание на неделю
async def show_week_schedule(update: Update, token):
    today = datetime.now(MOSCOW_TZ)
    start_of_week = today - timedelta(days=today.weekday())
    week_schedule = ""

    for i in range(5):
        date = (start_of_week + timedelta(days=i)).strftime("%Y-%m-%d")
        day_name = get_day_name_in_russian((start_of_week + timedelta(days=i)).weekday())
        schedule_info = get_schedule(date, update.message.from_user.id)
        week_schedule += f"📅 {day_name} ({date}):\n{schedule_info}\n"

    await update.message.reply_text(week_schedule)

async def get_next_week_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(MOSCOW_TZ)
    start_of_next_week = today + timedelta(days=(7 - today.weekday()))  # Получаем начало следующей недели
    next_week_schedule = ""

    for i in range(5):  # Понедельник - Пятница
        date = (start_of_next_week + timedelta(days=i)).strftime("%Y-%m-%d")
        day_name = get_day_name_in_russian((start_of_next_week + timedelta(days=i)).weekday())
        schedule_info = get_schedule(date, update.message.from_user.id)
        next_week_schedule += f"📅 {day_name} ({date}):\n{schedule_info}\n"

    await update.message.reply_text(next_week_schedule)

# Основной обработчик ошибок
async def handle_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка обработки сообщения: {context.error}")

def main():
    start_time = time.time()  # Фиксируем время старта

    application = Application.builder().token(BOT_TOKEN).build()

    # Обработчик команды /start
    application.add_handler(CommandHandler("start", start))

    conversation_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^Войти$'), login)],
        states={
            LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_login)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
        },
        fallbacks=[],
    )

    application.add_handler(conversation_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_date_request))

    elapsed_time = time.time() - start_time
    elapsed_time_str = f"{elapsed_time:.2f} секунд"

    # Логируем информацию о запуске бота
    logger.info(f"💻 Бот запущен! Время на полный запуск: {elapsed_time_str}")

    # Запускаем бота
    application.run_polling()

if __name__ == "__main__":
    main()