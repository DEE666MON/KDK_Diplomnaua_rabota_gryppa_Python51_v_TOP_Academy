from pathlib import Path
import sqlite3
import logging
import os
import shutil
from datetime import datetime
import time
import Backend_logic.bel as be

APP_NAME_NORMALIZATION = '''
CASE 
    WHEN app_name LIKE '%Chrome%' OR app_name LIKE '%Google Chrome%' THEN 'Chrome'
    WHEN app_name LIKE '%Browser%' OR app_name LIKE '%Yandex%' OR app_name LIKE '%Яндекс%' THEN 'Yandex Browser'
    WHEN app_name LIKE '%Word%' THEN 'Microsoft Word'
    WHEN app_name LIKE '%Excel%' THEN 'Microsoft Excel'
    WHEN app_name LIKE '%PowerPoint%' THEN 'Microsoft PowerPoint'
    WHEN app_name LIKE '%Code%' OR app_name LIKE '%Visual Studio Code%' OR app_name LIKE '%Visual Studio%' THEN 'VS Code'
    WHEN app_name LIKE '%PyCharm%' OR app_name LIKE '%PyCharm64%' OR app_name LIKE '%.py%' THEN 'PyCharm'
    WHEN app_name LIKE '%Telegram%' THEN 'Telegram'
    WHEN app_name LIKE '%Discord%' THEN 'Discord'
    WHEN app_name LIKE '%Spotify%' THEN 'Spotify'
    WHEN app_name LIKE '%Factorio%' THEN 'Factorio'
    WHEN app_name LIKE '%Steam%' THEN 'Steam'
    ELSE app_name 
END as app
'''
DB_PATH = Path(__file__).with_name("time_tracker.db")

def get_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as ex:
        be.log_error(f"Ошибка! Не удалось подключиться к базе данных (get_connection).\n{ex}")
        return None

def init_database():
    # Создание необходимых таблиц
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_name TEXT,
            category TEXT,
            date TEXT,
            duration INTEGER,
            session_id INTEGER
        )''')
        c.execute('''
        CREATE TABLE IF NOT EXISTS screenshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            timestamp TEXT,
            session_id INTEGER
        )''')
        c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')
        c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TEXT,
            end_time TEXT,
            duration INTEGER,
            total_activity INTEGER,
            idle_time INTEGER,
            app_switches INTEGER
        )''')
        c.execute("CREATE INDEX IF NOT EXISTS idx_activities_date ON activities(date)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_activities_session ON activities(session_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_screenshots_timestamp ON screenshots(timestamp)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(start_time)")
        conn.commit()
        conn.close()
        logging.info("Успешное подключение к базе данных.")
    except Exception as ex:
        be.log_error(f"Ошибка! Не удалось подключиться к базе данных (init_database).\n{ex}")

def auto_backup_database():
    # Автоматическое резервное копирование БД
    try:
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        backup_name = f"time_tracker_backup_{datetime.now().strftime('%Y-%m-%d')}.db"
        backup_path = os.path.join(backup_dir, backup_name)
        shutil.copy2(DB_PATH, backup_path)
        current_time = time.time()
        for filename in os.listdir(backup_dir):
            filepath = os.path.join(backup_dir, filename)
            if os.path.isfile(filepath) and (current_time - os.path.getmtime(filepath)) > 30 * 86400:
                os.remove(filepath)
        logging.info(f"Копия БД была создана: {backup_path}.")
    except Exception as ex:
        be.log_error(f"Ошибка! Не удалось создать копию БД.\n{ex}")

def database_optimazer():
    try:
        conn = get_connection()
        c = conn.cursor()
        # VACUUM для оптимизации
        c.execute("VACUUM")
        # Анализ для улучшения производительности запросов
        c.execute("ANALYZE")
        conn.close()
        logging.info("БД оптимизирована.")
    except Exception as ex:
        be.log_error(f"Ошибка! Не удалось оптимизировать БД.\n{ex}")

def insert_session(start_time):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute('''
            INSERT INTO sessions (start_time, duration, total_activity, idle_time, app_switches) 
            VALUES (?, ?, ?, ?, ?)
        ''', (start_time, 0, 0, 0, 0))
        session_id = c.lastrowid
        conn.commit()
        conn.close()
        logging.info(f"Новая сессия начата: {session_id} в {start_time}")
        return session_id
    except Exception as ex:
        be.log_error(f"Ошибка! Не удалось начать сессию (insert_session).\n{ex}")
        return None

def insert_activity_db(app_name, category, time, duration, session_id):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute('''
            INSERT INTO activities (app_name, category, date, duration, session_id) 
            VALUES (?, ?, ?, ?, ?)
            ''', (app_name, category, time, duration, session_id))
        conn.commit()
        conn.close()
    except Exception as ex:
        be.log_error(f"Ошибка! Не удалось сохранить активность пользователя (insert_activity_db).\n{ex}")

def insert_screenshot_db(filename, time, session_id):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute('''
            INSERT INTO screenshots (filename, timestamp, session_id) 
            VALUES (?, ?, ?)
            ''', (filename, time, session_id))
        conn.commit()
        conn.close()
    except Exception as ex:
        be.log_error(f"Ошибка! Не удалось создать и сохранить скриншот (insert_screenshot_db).\n{ex}")

def insert_settings_db(key, value):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()
        conn.close()
    except Exception as ex:
        be.log_error(f"Ошибка! Не удалось сохранить настройки в БД (insert_settings_db).\n{ex}")

def update_session_db(end_time, duration, total_activity, idle_time, app_switches, session_id):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute('''
                UPDATE sessions 
                SET end_time = ?, duration = ?, total_activity = ?, idle_time = ?, app_switches = ?
                WHERE id = ?
            ''', (end_time, duration, total_activity, idle_time, app_switches, session_id))
        conn.commit()
        conn.close()
        logging.info(f"Успешное выполнение фукции 'update_session_db'.")
    except Exception as ex:
        be.log_error(f"Ошибка! Не удалось закончить сессию (update_session_db).\n{ex}")

def get_session_by_START_TIME_db(today_str):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute('''
            SELECT start_time, duration, total_activity, app_switches, idle_time
            FROM sessions 
            WHERE substr(start_time, 1, 10) = ?
            ORDER BY start_time DESC
        ''', (today_str,))
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as ex:
        be.log_error(f"Ошибка! Не удалось сформировать анализ сессий (get_session_by_START_TIME_db).\n{ex}")
        return None

def get_session_by_DURATION_and_START_TIME_db():
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute('''
            SELECT 
                substr(start_time, 1, 10) as day,
                COUNT(*) as session_count,
                SUM(duration) as total_duration,
                AVG(duration) as avg_duration,
                AVG(CASE WHEN duration > 0 THEN CAST(total_activity AS FLOAT) / duration ELSE 0 END) * 100 as avg_productivity
            FROM sessions 
            WHERE duration > 0
                AND substr(start_time, 1, 10) >= date('now', '-30 days')
            GROUP BY substr(start_time, 1, 10)
            ORDER BY day DESC
        ''')
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as ex:
        be.log_error(f"Ошибка! Не удалось сформировать анализ сессий (get_session_by_DURATION_and_START_TIME_db).\n{ex}")
        return None

def get_first_info_from_activities_by_date_for_history_db():
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT DISTINCT date FROM activities ORDER BY date DESC")
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as ex:
        be.log_error(f"Не удалось получить данные для окна истории активности (get_first_info_from_activities_by_date_for_history_db).\n{ex}")
        return None

def get_info_for_history_db(date_var):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute('''
            SELECT 
                CASE 
                    WHEN app_name LIKE '%Chrome%' THEN 'Chrome'
                    ELSE app_name 
                END as app,
                SUM(duration) as total_time, 
                category
            FROM activities 
            WHERE date = ?
            GROUP BY app
            ORDER BY total_time DESC
        ''', (date_var,))
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as ex:
        be.log_error(f"Не удалось получить данные для окна истории активности (get_first_info_from_activities_by_date_for_history_db).\n{ex}")
        return None

def get_info_for_weekly_stats():
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute('''
            SELECT date, SUM(duration) as total_time
            FROM activities 
            WHERE date >= date('now', '-7 days')
            GROUP BY date
            ORDER BY date
        ''')
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as ex:
        be.log_error(f"Не удалось получить данные для окна недельной статистики (get_info_for_weekly_stats).\n{ex}")
        return None

def get_info_for_detailed_stats(flag=True):
    try:
        conn = get_connection()
        c = conn.cursor()
        if flag:
            c.execute('''
                SELECT date, SUM(duration) as total
                FROM activities 
                WHERE date >= date('now', '-30 days')
                GROUP BY date
                ORDER BY date DESC
            ''')
        else:
            c.execute('''
                SELECT category, SUM(duration) as total
                FROM activities 
                WHERE date >= date('now', '-30 days')
                GROUP BY category
                ORDER BY total DESC
            ''')
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as ex:
        be.log_error(f"Не удалось получить данные для окна детальной статистики (get_info_for_detailed_stats).\n{ex}")
        return None

def get_info_for_CSV():
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT date, app_name, category, duration FROM activities ORDER BY date DESC")
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as ex:
        be.log_error(f"Не удалось экспортировать данные в CSV.\n{ex}")
        return None

def get_session_by_SESSION_ID_db(session_id):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT SUM(duration) FROM activities WHERE session_id = ?", (session_id,))
        total_activity = c.fetchone()[0] or 0
        conn.close()
        logging.info(f"Успешное выполнение фукции 'get_session_by_SESSION_ID_db'.")
        return total_activity
    except Exception as ex:
        be.log_error(f"Ошибка! Не удалось закончить сессию (get_session_by_SESSION_ID_db).\n{ex}")
        return None


def get_session_by_ID_db(session_id):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT start_time FROM sessions WHERE id = ?", (session_id,))
        start_row = c.fetchone()
        conn.close()
        logging.info(f"Успешное выполнение фукции 'get_session_by_ID_db'.")
        return start_row
    except Exception as ex:
        be.log_error(f"Ошибка! Не удалось закончить сессию (get_session_by_ID_db).\n{ex}")
        return None

def get_settings_db():
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT key, value FROM settings")
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as ex:
        be.log_error(f"Ошибка! Не удалось загрузить настройки из БД (get_settings_db).\n{ex}")
        return None

def get_special_activity_db(date_condition, limit):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f'''
        SELECT {APP_NAME_NORMALIZATION},
        SUM(duration) as total_time, 
        category
        FROM activities 
        WHERE {date_condition}
        GROUP BY app
        ORDER BY total_time DESC
        LIMIT {limit}
        ''')
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as ex:
        be.log_error(f"Ошибка! Не удалось сформировать отчёт (get_special_activity_db).\n{ex}")
        return None

def get_stats_status_by_DATE_db(today, flag=True):
    try:
        conn = get_connection()
        c = conn.cursor()
        if flag:
            c.execute("SELECT COUNT(*), SUM(duration) FROM activities WHERE date = ?", (today,))
            count, total = c.fetchone()
            conn.close()
            return count, total
        else:
            c.execute("SELECT SUM(duration) FROM activities WHERE date = ?", (today,))
            total = c.fetchone()[0] or 0
            conn.close()
            return total
    except Exception as ex:
        be.log_error(f"Ошибка! Не удалось обновить статус-бар (get_stats_status_by_DATE_db).\n{ex}")
        return None

def get_stats_status_by_ID_db(id):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT duration FROM sessions WHERE id = ?", (id,))
        session = c.fetchone()
        conn.close()
        return  session
    except Exception as ex:
        be.log_error(f"Ошибка! Не удалось обновить статус-бар (get_stats_status_by_ID_db).\n{ex}")
        return None

def get_info_for_refresh_stats_view(today, flag=True):
    try:
        conn = get_connection()
        c = conn.cursor()
        if flag:
            c.execute('''
                SELECT category, SUM(duration) as total
                FROM activities 
                WHERE date = ?
                GROUP BY category
            ''', (today,))
        else:
            c.execute(f'''
                SELECT {APP_NAME_NORMALIZATION},
                SUM(duration) as total_time
                FROM activities 
                WHERE date = ?
                GROUP BY app
                ORDER BY total_time DESC
                LIMIT 10
            ''', (today,))
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as ex:
        be.log_error(f"Не удалось получить данные для отображения статистики (get_info_for_refresh_stats_view).\n{ex}")
        return None