import logging
from logging.handlers import RotatingFileHandler
import sys

def setup_logging():
    # Настройка логирования с поддержкой UTF-8
    handler = RotatingFileHandler(
        'time_tracker.log',
        maxBytes=5 * 1024 * 1024,  # 5 МБ
        backupCount=3,
        encoding='utf-8'
    )
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(handler)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)


def log_error(error):
    # Логирование ошибок
    logging.error(str(error))
    print(f"Ошибка: {error}")

def clean_for_csv(text):
    # Очищает текст от символов, которые могут нарушить CSV
    import re
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F1E0-\U0001F1FF"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        u"\U0001F900-\U0001F9FF"
        u"\U0001FA70-\U0001FAFF"
        "]+", flags=re.UNICODE)
    clean_text = emoji_pattern.sub(r'', text)
    clean_text = clean_text.replace(',', ';').replace('"', "'")
    return clean_text.strip()