"""
Этот файл конфига для Telegram-бота

Всё что не используется в самом боте нужно вынести в отдельный конфиг парсинга сайта!!! 
"""

# Токен бота из бота @BotFather
BOT_TOKEN = "7787262890:AAFoBAcSLFysInDB_hOkPiFcDRvXcHksh2o"
APPLICATION_KEY = "6a56a5df2667e65aab73ce76d1dd737f7d1faef9c52e8b8c55ac75f565d8e8a6"

# URL для получения массива с расписанием пар с сервера сайта
SCHEDULE_URL = "https://msapi.top-academy.ru/api/v2/schedule/operations/get-by-date?date_filter={}"

# Прочие данные для парсинга сайта (для заголовков)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 YaBrowser/24.10.0.0 Safari/537.36"
ORIGIN = "https://journal.top-academy.ru"
REFERER = "https://journal.top-academy.ru/"

# Новый параметр для получения URL для авторизации пользователей, чтобы получать актуальные токены
AUTH_URL = "https://msapi.top-academy.ru/api/v2/auth/login"  # Пример URL для авторизации, укажите реальный, если он другой
