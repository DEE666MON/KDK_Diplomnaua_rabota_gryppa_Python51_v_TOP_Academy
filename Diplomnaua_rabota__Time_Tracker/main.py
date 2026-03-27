import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import queue
import os
import io
import sys
import logging
from datetime import datetime
import time
import pystray
import ctypes
from PIL import Image, ImageDraw, ImageGrab, ImageTk
import pygetwindow as gw
import csv
import Backend_logic.bel as be
import Database_logic.dbl as db

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

class TimeTrackerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Time Tracker")
        window_w, window_h = 800, 750
        screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x, y = (screen_w - window_w) // 2, (screen_h - window_h) // 2
        self.root.geometry(f"{window_w}x{window_h}+{x}+{y}")
        self.root.minsize(800, 750)
        be.setup_logging()
        self.current_app = "Неизвестно"
        self.current_app_start = time.time()
# ===== Настройки по умолчанию ===== #
        self.screenshot_interval = 600  # 10 минут в секундах
        self.screenshot_delete_interval = 7 # дни после которых будет удалён скриншот
        self.min_activity_time = 5  # минимальное время активности в секундах
        self.idle_threshold = 300  # порог бездействия (5 минут)
# ===== Настройки по умолчанию ===== #
        self.notifications_enabled = True
        self.auto_backup_enabled = True
        self.load_settings()
        self.queue = queue.Queue()
        self.process_queue()
        self.setup_ui()
        self.setup_menu()
        self.setup_status_bar()
        self.setup_hotkeys()
        db.init_database()
        self.running = True
        self.monitor_thread = threading.Thread(target=self.monitor_activity, daemon=True)
        self.monitor_thread.start()
        self.update_live_stats()
        self.setup_tray()
        self.cleanup_old_screenshots(self.screenshot_delete_interval)
        if self.auto_backup_enabled:
            db.auto_backup_database()
        # Обработка закрытия окна
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)

    def setup_menu(self):
        # Создание меню в верхнем левом углу
        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)
        file_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Экспорт в CSV (простой)", command=self.export_to_csv)
        file_menu.add_command(label="Экспорт в CSV (расширенный)", command=self.export_to_csv_advanced)
        file_menu.add_separator()
        file_menu.add_command(label="Оптимизировать БД", command=self.optimize_database)
        file_menu.add_separator()
        file_menu.add_command(label="Спрятать", command=self.hide_window, accelerator="Space")
        file_menu.add_command(label="Выход", command=self.quit_app, accelerator="Escape")
        view_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Вид", menu=view_menu)
        view_menu.add_command(label="История", command=self.show_history)
        view_menu.add_command(label="Недельная статистика", command=self.show_weekly_stats)
        view_menu.add_command(label="Детальная статистика", command=self.show_detailed_stats)
        view_menu.add_command(label="Анализ сессий", command=self.show_session_analysis)
        view_menu.add_command(label="Просмотр скриншотов", command=self.show_screenshots)
        settings_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Настройки", menu=settings_menu)
        settings_menu.add_command(label="Параметры", command=self.open_settings, accelerator="F3")
        settings_menu.add_command(label="Очистить старые скриншоты", command=lambda: self.cleanup_old_screenshots(self.screenshot_delete_interval))
        help_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Справка", menu=help_menu)
        help_menu.add_command(label="Горячие клавиши", command=self.show_help, accelerator="F1")
        help_menu.add_command(label="О программе", command=self.show_about)

    def setup_status_bar(self):
        # Создание статус-бара
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(side='bottom', fill='x')
        self.status_label = ttk.Label(self.status_bar, text="Готов к работе", relief='sunken', anchor='w')
        self.status_label.pack(side='left', fill='x', expand=True)
        self.stats_status_label = ttk.Label(self.status_bar, text="", relief='sunken', width=50)
        self.stats_status_label.pack(side='right')

    def setup_hotkeys(self):
        # Настройка горячих клавиш
        self.root.bind('<F1>', lambda e: self.show_help())
        self.root.bind('<F2>', lambda e: self.generate_report())
        self.root.bind('<F3>', lambda e: self.open_settings())
        self.root.bind('<space>', lambda e: self.hide_window())
        self.root.bind('<Escape>', lambda e: self.quit_app())

    def show_help(self):
        # Окно справки о программе
        help_window = tk.Toplevel(self.root)
        help_window.title("Справка и горячие клавиши")
        window_w, window_h = 600, 500
        screen_w, screen_h = help_window.winfo_screenwidth(), help_window.winfo_screenheight()
        x, y = (screen_w - window_w) // 2, (screen_h - window_h) // 2
        help_window.geometry(f"{window_w}x{window_h}+{x}+{y}")
        help_window.minsize(600, 500)
        help_window.resizable(False, False)
        help_window.transient(self.root)
        help_text = """
        Справка:
        - Программа автоматически отслеживает активные окна;
        - Делает скриншоты каждые 10 минут (по-умолчанию) 
        или время установленное пользователем;
        - Ведет статистику по категориям;
        - Отслеживает рабочие сессии и продуктивность.
        
        Горячие клавиши:
        Двойной клик по иконке в трее - показать окно
        F1 - Показать эту справку
        F2 - Сформировать отчет за сегодня
        F3 - Открыть настройки
        Space - Скрыть окно в трей
        Escape - Выход из программы
        """
        ttk.Label(help_window, text=help_text, justify='left', font=("Arial", 14)).pack(padx=20, pady=20)

    def show_about(self):
        # Окно информации о программе
        about_window = tk.Toplevel(self.root)
        about_window.title("О программе")
        window_w, window_h = 600, 450
        screen_w, screen_h = about_window.winfo_screenwidth(), about_window.winfo_screenheight()
        x, y = (screen_w - window_w) // 2, (screen_h - window_h) // 2
        about_window.geometry(f"{window_w}x{window_h}+{x}+{y}")
        about_window.minsize(600, 450)
        about_window.resizable(False, False)
        about_window.transient(self.root)
        about_text = """
        Time Tracker

        Программа для учета рабочего времени
        с автоматическим созданием скриншотов.

        Особенности:
        - Отслеживание активных окон
        - Категоризация приложений
        - Автоматические скриншоты
        - Детальная статистика
        - Анализ рабочих сессий
        - Экспорт данных

        Разработано на Python с использованием Tkinter
        """
        ttk.Label(about_window, text=about_text, justify='center', font=("Arial", 14)).pack(padx=20, pady=20)

    def setup_ui(self):
        # Создание основного интерфейса
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        self.stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.stats_frame, text="Статистика")
        current_frame = ttk.LabelFrame(self.stats_frame, text="Текущая активность", padding=10)
        current_frame.pack(fill='x', padx=10, pady=10)
        self.current_app_label = ttk.Label(current_frame, text="Приложение: ", font=('Arial', 11, 'bold'))
        self.current_app_label.pack(anchor='w')
        self.current_time_label = ttk.Label(current_frame, text="Время: 0 сек", font=('Arial', 10))
        self.current_time_label.pack(anchor='w')
        self.idle_label = ttk.Label(current_frame, text="", font=('Arial', 9))
        self.idle_label.pack(anchor='w')
        today_frame = ttk.LabelFrame(self.stats_frame, text="Статистика за сегодня", padding=10)
        today_frame.pack(fill='both', expand=True, padx=10, pady=10)
        self.total_time_label = ttk.Label(today_frame, text="Всего времени: 0 ч 0 мин", font=('Arial', 11, 'bold'))
        self.total_time_label.pack(anchor='w', pady=5)
        self.categories_label = ttk.Label(today_frame, text="По категориям:", font=('Arial', 10, 'bold'))
        self.categories_label.pack(anchor='w', pady=(10, 5))
        self.categories_frame = ttk.Frame(today_frame)
        self.categories_frame.pack(fill='x', pady=5)
        categories_frame = ttk.Frame(today_frame)
        categories_frame.pack(fill='x', pady=5)
        self.category_labels = {}
        categories = ['browser', 'editor', 'office', 'communication', 'media', 'game', 'system', 'development', 'other']
        left_frame = ttk.Frame(categories_frame)
        left_frame.pack(side='left', fill='both', expand=True)
        right_frame = ttk.Frame(categories_frame)
        right_frame.pack(side='right', fill='both', expand=True)
        for i, cat in enumerate(categories[:5]):
            frame = ttk.Frame(left_frame)
            frame.pack(fill='x', pady=2)
            name = ttk.Label(frame, text=f"{self.get_category_name(cat)}:", width=15, anchor='w')
            name.pack(side='left')
            value = ttk.Label(frame, text="0 мин", anchor='e')
            value.pack(side='right')
            self.category_labels[cat] = value
        for i, cat in enumerate(categories[5:]):
            frame = ttk.Frame(right_frame)
            frame.pack(fill='x', pady=2)
            name = ttk.Label(frame, text=f"{self.get_category_name(cat)}:", width=15, anchor='w')
            name.pack(side='left')
            value = ttk.Label(frame, text="0 мин", anchor='e')
            value.pack(side='right')
            self.category_labels[cat] = value
        self.top_apps_label = ttk.Label(today_frame, text="Топ приложений:", font=('Arial', 10, 'bold'))
        self.top_apps_label.pack(anchor='w', pady=(10, 5))
        self.top_apps_frame = ttk.Frame(today_frame)
        self.top_apps_frame.pack(fill='both', expand=True)
        self.top_apps = []
        for i in range(10):
            frame = ttk.Frame(self.top_apps_frame)
            frame.pack(fill='x', pady=2)
            app_name = ttk.Label(frame, text=f"{i + 1}. ", width=100, anchor='w')
            app_name.pack(side='left')
            app_time = ttk.Label(frame, text="0 мин", anchor='e')
            app_time.pack(side='right')
            self.top_apps.append((app_name, app_time))
        ttk.Button(today_frame, text="Обновить статистику", command=self.refresh_stats_view).pack(pady=10)
        self.reports_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.reports_frame, text="Отчёты")
        toolbar = ttk.Frame(self.reports_frame)
        toolbar.pack(fill='x', padx=10, pady=5)
        ttk.Button(toolbar, text="За сегодня", command=self.generate_report).pack(side='left', padx=2)
        ttk.Button(toolbar, text="За вчера", command=self.show_yesterday_report).pack(side='left', padx=2)
        ttk.Button(toolbar, text="За неделю", command=self.show_weekly_report).pack(side='left', padx=2)
        ttk.Button(toolbar, text="За месяц", command=self.show_monthly_report).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Экспорт в CSV (простой)", command=self.export_to_csv).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Экспорт в CSV (расширенный)", command=self.export_to_csv_advanced).pack(side='left', padx=2)
        tree_container = ttk.Frame(self.reports_frame)
        tree_container.pack(fill='both', expand=True, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(tree_container, orient='vertical')
        scrollbar.pack(side='right', fill='y')
        self.tree = ttk.Treeview(tree_container, columns=('Приложение', 'Время', 'Категория'), show='headings', yscrollcommand=scrollbar.set)
        self.tree.heading('Приложение', text='Приложение')
        self.tree.heading('Время', text='Время')
        self.tree.heading('Категория', text='Категория')
        self.tree.column('Приложение', width=400)
        self.tree.column('Время', width=100)
        self.tree.column('Категория', width=100)
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.tree.yview)

    def show_session_analysis(self):
        # Открытие окна анализа сессий
        analysis_window = tk.Toplevel(self.root)
        analysis_window.title("Анализ рабочих сессий")
        window_w, window_h = 1000, 700
        screen_w, screen_h = analysis_window.winfo_screenwidth(), analysis_window.winfo_screenheight()
        x, y = (screen_w - window_w) // 2, (screen_h - window_h) // 2
        analysis_window.geometry(f"{window_w}x{window_h}+{x}+{y}")
        analysis_window.minsize(1000, 700)
        analysis_window.transient(self.root)
        notebook = ttk.Notebook(analysis_window)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        today_frame = ttk.Frame(notebook)
        notebook.add(today_frame, text="Сегодняшние сессии")
        tree_container = ttk.Frame(today_frame)
        tree_container.pack(fill='both', expand=True, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(tree_container, orient='vertical')
        scrollbar.pack(side='right', fill='y')
        today_tree = ttk.Treeview(
            tree_container,
            columns=('Время', 'Длительность', 'Активность', 'Переключений', 'Бездействие', 'Продуктивность'),
            show='headings',
            yscrollcommand=scrollbar.set
        )
        today_tree.heading('Время', text='Время')
        today_tree.heading('Длительность', text='Длительность')
        today_tree.heading('Активность', text='Активное время')
        today_tree.heading('Переключений', text='Переключений')
        today_tree.heading('Бездействие', text='Бездействие')
        today_tree.heading('Продуктивность', text='Продуктивность')
        today_tree.column('Время', width=120)
        today_tree.column('Длительность', width=120)
        today_tree.column('Активность', width=120)
        today_tree.column('Переключений', width=100)
        today_tree.column('Бездействие', width=120)
        today_tree.column('Продуктивность', width=100)
        today_tree.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=today_tree.yview)
        today_str = datetime.now().strftime("%Y-%m-%d")
        tt_rows = db.get_session_by_START_TIME_db(today_str)
        for row in tt_rows:
            try:
                start_time = row[0]
                if ' ' in start_time:
                    time_part = start_time.split(' ')[1]
                else:
                    time_part = start_time
                start_time_display = time_part
            except:
                start_time_display = "?"
            productivity = (row[2] / row[1] * 100) if row[1] and row[1] > 0 else 0
            today_tree.insert('', 'end', values=(
                start_time_display,
                self.format_time(row[1]),
                self.format_time(row[2]),
                row[3],
                self.format_time(row[4]),
                f"{productivity:.1f}%"
            ))
        history_frame = ttk.Frame(notebook)
        notebook.add(history_frame, text="История сессий")
        tree_container2 = ttk.Frame(history_frame)
        tree_container2.pack(fill='both', expand=True, padx=10, pady=10)
        scrollbar2 = ttk.Scrollbar(tree_container2, orient='vertical')
        scrollbar2.pack(side='right', fill='y')
        history_tree = ttk.Treeview(
            tree_container2,
            columns=('Дата', 'Кол-во', 'Общее время', 'Среднее время', 'Ср. продуктивность'),
            show='headings',
            yscrollcommand=scrollbar2.set
        )
        history_tree.heading('Дата', text='Дата')
        history_tree.heading('Кол-во', text='Кол-во сессий')
        history_tree.heading('Общее время', text='Общее время')
        history_tree.heading('Среднее время', text='Среднее время')
        history_tree.heading('Ср. продуктивность', text='Ср. продуктивность')
        history_tree.column('Дата', width=120)
        history_tree.column('Кол-во', width=100)
        history_tree.column('Общее время', width=120)
        history_tree.column('Среднее время', width=120)
        history_tree.column('Ср. продуктивность', width=120)
        history_tree.pack(side='left', fill='both', expand=True)
        scrollbar2.config(command=history_tree.yview)
        ht_rows = db.get_session_by_DURATION_and_START_TIME_db()
        logging.info(f"Найдено записей в history_tree: {len(ht_rows)}")
        if len(ht_rows) > 0:
            logging.info(f"Первая запись: {ht_rows[0]} — {ht_rows[0][0]}, {ht_rows[0][1]}, {ht_rows[0][2]}, {ht_rows[0][3]}, {ht_rows[0][4]}")
        for row in ht_rows:
            try:
                date_display = row[0]  # Уже в формате YYYY-MM-DD
                history_tree.insert('', 'end', values=(
                    date_display,
                    row[1],
                    self.format_time(row[2]),
                    self.format_time(row[3]),
                    f"{row[4]:.1f}%" if row[4] else "0%"
                ))
            except Exception as ex:
                be.log_error(f"Ошибка при вставке данных в history_tree: {ex}")
                print(f"Ошибка с row: {row}")
        if len(ht_rows) == 0:
            history_tree.insert('', 'end', values=('Нет данных за последние 30 дней', '-', '-', '-', '-'))

    def show_history(self):
        # Открытие окна с историей за выбранный день
        history_window = tk.Toplevel(self.root)
        history_window.title("История активности")
        window_w, window_h = 900, 650
        screen_w, screen_h = history_window.winfo_screenwidth(), history_window.winfo_screenheight()
        x, y = (screen_w - window_w) // 2, (screen_h - window_h) // 2
        history_window.geometry(f"{window_w}x{window_h}+{x}+{y}")
        history_window.minsize(900, 650)
        history_window.transient(self.root)
        rows = db.get_first_info_from_activities_by_date_for_history_db()
        dates = [row[0] for row in rows]
        if not dates:
            ttk.Label(history_window, text="Нет данных для отображения...").pack(pady=20)
            return
        control_frame = ttk.Frame(history_window)
        control_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(control_frame, text="Выберите дату:").pack(side='left', padx=5)
        date_var = tk.StringVar(value=dates[0])
        date_combo = ttk.Combobox(control_frame, textvariable=date_var, values=dates, width=15)
        date_combo.pack(side='left', padx=5)
        ttk.Button(control_frame, text="Загрузить", command=lambda: load_history()).pack(side='left', padx=5)
        tree_container = ttk.Frame(history_window)
        tree_container.pack(fill='both', expand=True, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(tree_container, orient='vertical')
        scrollbar.pack(side='right', fill='y')
        tree = ttk.Treeview(tree_container, columns=('Приложение', 'Время', 'Категория'), show='headings', yscrollcommand=scrollbar.set)
        tree.heading('Приложение', text='Приложение')
        tree.heading('Время', text='Время')
        tree.heading('Категория', text='Категория')
        tree.column('Приложение', width=600)
        tree.column('Время', width=100)
        tree.column('Категория', width=100)
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=tree.yview)

        def load_history():
            for row in tree.get_children():
                tree.delete(row)
            rows = db.get_info_for_history_db(date_var.get())
            for app_name, seconds, category in rows:
                display_time = self.format_time(seconds)
                category_name = self.get_category_name(category)
                icon = self.get_app_icon(app_name)
                tree.insert('', 'end', values=(f"{icon} {app_name}", display_time, category_name))

        load_history()

    def show_weekly_stats(self):
        # Открытие окна статистики по дням недели
        stats_window = tk.Toplevel(self.root)
        stats_window.title("Недельная статистика")
        window_w, window_h = 600, 500
        screen_w, screen_h = stats_window.winfo_screenwidth(), stats_window.winfo_screenheight()
        x, y = (screen_w - window_w) // 2, (screen_h - window_h) // 2
        stats_window.geometry(f"{window_w}x{window_h}+{x}+{y}")
        stats_window.minsize(600, 500)
        stats_window.resizable(False, False)
        stats_window.transient(self.root)
        rows = db.get_info_for_weekly_stats()
        days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        stats = {}
        total_week = 0
        for date, seconds in rows:
            day_of_week = datetime.strptime(date, "%Y-%m-%d").weekday()
            stats[day_of_week] = seconds
            total_week += seconds
        main_frame = ttk.Frame(stats_window, padding=20)
        main_frame.pack(fill='both', expand=True)
        ttk.Label(main_frame, text="Статистика за последние 7 дней", font=('Arial', 14, 'bold')).pack(pady=10)
        ttk.Label(main_frame, text=f"Всего за неделю: {self.format_time(total_week)}", font=('Arial', 12)).pack(pady=5)
        ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=10)
        for i, day in enumerate(days):
            seconds = stats.get(i, 0)
            frame = ttk.Frame(main_frame)
            frame.pack(fill='x', pady=5)
            ttk.Label(frame, text=f"{day}:", width=15, anchor='w', font=('Arial', 10)).pack(side='left')
            ttk.Label(frame, text=self.format_time(seconds), anchor='e', font=('Arial', 10, 'bold')).pack(side='right')
        today = datetime.now().weekday()
        if today in stats:
            ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=10)
            ttk.Label(main_frame, text=f"Сегодня: {self.format_time(stats[today])}", font=('Arial', 11, 'bold')).pack()

    def show_detailed_stats(self):
        # Открытие окна детальной статистики
        stats_window = tk.Toplevel(self.root)
        stats_window.title("Детальная статистика")
        window_w, window_h = 600, 400
        screen_w, screen_h = stats_window.winfo_screenwidth(), stats_window.winfo_screenheight()
        x, y = (screen_w - window_w) // 2, (screen_h - window_h) // 2
        stats_window.geometry(f"{window_w}x{window_h}+{x}+{y}")
        stats_window.minsize(600, 400)
        stats_window.transient(self.root)
        notebook = ttk.Notebook(stats_window)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        daily_frame = ttk.Frame(notebook)
        notebook.add(daily_frame, text="По дням (последние 30 дней)")
        daily_tree = ttk.Treeview(daily_frame, columns=('Дата', 'Время'), show='headings')
        daily_tree.heading('Дата', text='Дата')
        daily_tree.heading('Время', text='Время')
        daily_tree.pack(fill='both', expand=True)
        rows = db.get_info_for_detailed_stats()
        for date, seconds in rows:
            daily_tree.insert('', 'end', values=(date, self.format_time(seconds)))
        category_frame = ttk.Frame(notebook)
        notebook.add(category_frame, text="По категориям (месяц)")
        category_tree = ttk.Treeview(category_frame, columns=('Категория', 'Время', '%'), show='headings')
        category_tree.heading('Категория', text='Категория')
        category_tree.heading('Время', text='Время')
        category_tree.heading('%', text='% от общего времени')
        category_tree.pack(fill='both', expand=True)
        rows = db.get_info_for_detailed_stats(False)
        total_all = sum(row[1] for row in rows)
        for category, seconds in rows:
            percentage = (seconds / total_all * 100) if total_all > 0 else 0
            category_tree.insert('', 'end', values=(
                self.get_category_name(category),
                self.format_time(seconds),
                f"{percentage:.1f}%"
            ))

    def show_screenshots(self):
        # Открытие окна со скриншотами и предпросмотром
        screenshots_window = tk.Toplevel(self.root)
        screenshots_window.title("Скриншоты")
        window_w, window_h = 1000, 700
        screen_w, screen_h = screenshots_window.winfo_screenwidth(), screenshots_window.winfo_screenheight()
        x, y = (screen_w - window_w) // 2, (screen_h - window_h) // 2
        screenshots_window.geometry(f"{window_w}x{window_h}+{x}+{y}")
        screenshots_window.minsize(1000, 700)
        screenshots_window.transient(self.root)
        screenshots_dir = "screenshots"
        if not os.path.exists(screenshots_dir):
            ttk.Label(screenshots_window, text="Папка со скриншотами не найдена").pack(pady=20)
            return
        screenshots = []
        for filename in os.listdir(screenshots_dir):
            if filename.endswith('.png'):
                filepath = os.path.join(screenshots_dir, filename)
                filetime = os.path.getmtime(filepath)
                screenshots.append((filename, filepath, filetime))
        screenshots.sort(key=lambda x: x[2], reverse=True)
        if not screenshots:
            ttk.Label(screenshots_window, text="Нет скриншотов").pack(pady=20)
            return
        main_panel = ttk.PanedWindow(screenshots_window, orient='horizontal')
        main_panel.pack(fill='both', expand=True, padx=10, pady=10)
        left_frame = ttk.Frame(main_panel)
        main_panel.add(left_frame, weight=1)
        ttk.Label(left_frame, text="Список скриншотов:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=5)
        listbox_frame = ttk.Frame(left_frame)
        listbox_frame.pack(fill='both', expand=True)
        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side='right', fill='y')
        listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set, height=20)
        listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=listbox.yview)
        for filename, filepath, filetime in screenshots:
            date_str = datetime.fromtimestamp(filetime).strftime("%Y-%m-%d %H:%M:%S")
            listbox.insert(tk.END, f"{date_str} - {filename}")
        right_frame = ttk.Frame(main_panel)
        main_panel.add(right_frame, weight=2)
        ttk.Label(right_frame, text="Предпросмотр:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=5)
        preview_label = ttk.Label(right_frame, text="Выберите скриншот для просмотра")
        preview_label.pack(expand=True)

        def on_select(event):
            selection = listbox.curselection()
            if selection:
                filename, filepath, filetime = screenshots[selection[0]]
                try:
                    img = Image.open(filepath)
                    img.thumbnail((500, 400))
                    photo = ImageTk.PhotoImage(img)
                    preview_label.config(image=photo, text="")
                    preview_label.image = photo
                except Exception as e:
                    preview_label.config(text=f"Не удалось загрузить: {e}", image="")

        def open_screenshot():
            selection = listbox.curselection()
            if selection:
                filename, filepath, _ = screenshots[selection[0]]
                os.startfile(filepath)

        def delete_screenshot():
            selection = listbox.curselection()
            if selection:
                if messagebox.askyesno("Подтверждение", "Удалить скриншот?"):
                    filename, filepath, _ = screenshots[selection[0]]
                    os.remove(filepath)
                    screenshots.pop(selection[0])
                    listbox.delete(selection[0])
                    preview_label.config(image="", text="Скриншот удален")
                    self.update_status(f"Скриншот {filename} удален")

        listbox.bind('<<ListboxSelect>>', on_select)
        button_frame = ttk.Frame(screenshots_window)
        button_frame.pack(fill='y', padx=10, pady=5)
        ttk.Button(button_frame, text="Открыть", command=open_screenshot).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(button_frame, text="Удалить", command=delete_screenshot).grid(row=0, column=1, padx=5, pady=5)

    def open_settings(self):
        # Открытие окна настроек
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Настройки")
        window_w, window_h = 350, 400
        screen_w, screen_h = settings_window.winfo_screenwidth(), settings_window.winfo_screenheight()
        x, y = (screen_w - window_w) // 2, (screen_h - window_h) // 2
        settings_window.geometry(f"{window_w}x{window_h}+{x}+{y}")
        settings_window.minsize(350, 400)
        settings_window.resizable(False, False)
        settings_window.transient(self.root)
        settings_window.grab_set()
        notebook = ttk.Notebook(settings_window)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        main_frame = ttk.Frame(notebook)
        notebook.add(main_frame, text="Основные")
        main_inner = ttk.Frame(main_frame, padding=20)
        main_inner.pack(fill='both', expand=True)
        ttk.Label(main_inner, text="Интервал скриншотов (минут):").pack(anchor='w', pady=5)
        screenshot_var = tk.StringVar(value=str(self.screenshot_interval // 60))
        ttk.Entry(main_inner, textvariable=screenshot_var, width=10).pack(anchor='w', pady=5)
        ttk.Label(main_inner, text="Минимальное время активности (сек):").pack(anchor='w', pady=5)
        min_activity_var = tk.StringVar(value=str(self.min_activity_time))
        ttk.Entry(main_inner, textvariable=min_activity_var, width=10).pack(anchor='w', pady=5)
        ttk.Label(main_inner, text="Порог бездействия (минут):").pack(anchor='w', pady=5)
        idle_var = tk.StringVar(value=str(self.idle_threshold // 60))
        ttk.Entry(main_inner, textvariable=idle_var, width=10).pack(anchor='w', pady=5)
        screenshot_frame = ttk.Frame(notebook)
        notebook.add(screenshot_frame, text="Скриншоты")
        screenshot_inner = ttk.Frame(screenshot_frame, padding=20)
        screenshot_inner.pack(fill='both', expand=True)
        ttk.Label(screenshot_inner, text="Хранить скриншоты (дней):").pack(anchor='w', pady=5)
        cleanup_var = tk.StringVar(value=str(self.screenshot_delete_interval))
        ttk.Entry(screenshot_inner, textvariable=cleanup_var, width=10).pack(anchor='w', pady=5)
        notifications_frame = ttk.Frame(notebook)
        notebook.add(notifications_frame, text="Уведомления")
        notifications_inner = ttk.Frame(notifications_frame, padding=20)
        notifications_inner.pack(fill='both', expand=True)
        notifications_var = tk.BooleanVar(value=self.notifications_enabled)
        ttk.Checkbutton(notifications_inner, text="Включить уведомления", variable=notifications_var).pack(anchor='w', pady=5)
        backup_var = tk.BooleanVar(value=self.auto_backup_enabled)
        ttk.Checkbutton(notifications_inner, text="Автоматическое резервное копирование", variable=backup_var).pack(anchor='w', pady=5)

        def save_settings():
            # Сохранение настроек приложения
            try:
                self.screenshot_interval = int(screenshot_var.get()) * 60
                self.screenshot_delete_interval = int(cleanup_var.get())
                self.min_activity_time = int(min_activity_var.get())
                self.idle_threshold = int(idle_var.get()) * 60
                self.notifications_enabled = notifications_var.get()
                self.auto_backup_enabled = backup_var.get()
                self.save_setting('screenshot_interval', self.screenshot_interval)
                self.save_setting('screenshot_delete_interval', self.screenshot_delete_interval)
                self.save_setting('min_activity_time', self.min_activity_time)
                self.save_setting('idle_threshold', self.idle_threshold)
                self.save_setting('notifications_enabled', self.notifications_enabled)
                self.save_setting('auto_backup_enabled', self.auto_backup_enabled)
                self.cleanup_old_screenshots(self.screenshot_delete_interval)
                messagebox.showinfo("Настройки", "Настройки сохранены")
                settings_window.destroy()
                self.update_status("Настройки сохранены")
            except ValueError:
                messagebox.showerror("Ошибка", "Пожалуйста, введите корректные числа.")

        button_frame = ttk.Frame(settings_window)
        button_frame.pack(fill='y', pady=10)
        ttk.Button(button_frame, text="Сохранить", command=save_settings).grid(row=0, column=0, padx=10)
        ttk.Button(button_frame, text="Отмена", command=settings_window.destroy).grid(row=0, column=1, padx=10)

    def export_to_csv(self):
        # Экспорт в CSV файл
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            try:
                rows = db.get_info_for_CSV()
                with open(filename, 'w', newline='', encoding='utf-8-sig') as file:
                    writer = csv.writer(file, delimiter=';', quoting=csv.QUOTE_ALL)
                    writer.writerow(['Дата', 'Приложение', 'Категория', 'Время (сек)', 'Время'])
                    for row in rows:
                        date, app_name, category, seconds = row
                        clean_app_name = be.clean_for_csv(app_name)
                        writer.writerow([
                            date,
                            clean_app_name,
                            category,
                            seconds,
                            self.format_time(seconds)
                        ])
                messagebox.showinfo("Экспорт завершен", f"Данные сохранены в {filename}\n\nСовет: При открытии в Excel выберите:\n- Разделитель: точка с запятой (;)\n- Кодировка: UTF-8")
                logging.info(f"Data exported to {filename}")
                self.update_status(f"Данные экспортированы в {filename}")
            except Exception as ex:
                messagebox.showerror("Ошибка", f"Не удалось экспортировать данные в CSV.\n{ex}")

    def export_to_csv_advanced(self):
        # Открытие окна Расширенного экспорта в CSV с выбором настроек
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Параметры экспорта")
        window_w, window_h = 400, 350
        screen_w, screen_h = settings_window.winfo_screenwidth(), settings_window.winfo_screenheight()
        x, y = (screen_w - window_w) // 2, (screen_h - window_h) // 2
        settings_window.geometry(f"{window_w}x{window_h}+{x}+{y}")
        settings_window.minsize(400, 350)
        settings_window.resizable(False, False)
        settings_window.transient(self.root)
        settings_window.grab_set()
        ttk.Label(settings_window, text="Выберите разделитель:").pack(pady=10)
        delimiter_var = tk.StringVar(value=";")
        ttk.Radiobutton(settings_window, text="Точка с запятой (;) - для Excel", variable=delimiter_var, value=";").pack()
        ttk.Radiobutton(settings_window, text="Запятая (,) - для других программ", variable=delimiter_var, value=",").pack()
        ttk.Label(settings_window, text="Кодировка:").pack(pady=10)
        encoding_var = tk.StringVar(value="utf-8-sig")
        ttk.Radiobutton(settings_window, text="UTF-8 (с BOM) - для Excel", variable=encoding_var, value="utf-8-sig").pack()
        ttk.Radiobutton(settings_window, text="UTF-8 (без BOM)", variable=encoding_var, value="utf-8").pack()
        ttk.Label(settings_window, text="Очистить эмодзи:").pack(pady=10)
        clean_emoji_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_window, text="Удалить эмодзи из названий", variable=clean_emoji_var).pack()
        def do_export():
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if filename:
                try:
                    rows = db.get_info_for_CSV()
                    with open(filename, 'w', newline='', encoding=encoding_var.get()) as file:
                        writer = csv.writer(file, delimiter=delimiter_var.get(), quoting=csv.QUOTE_ALL)
                        writer.writerow(['Дата', 'Приложение', 'Категория', 'Время (сек)', 'Время'])
                        for row in rows:
                            date, app_name, category, seconds = row
                            if clean_emoji_var.get():
                                app_name = be.clean_for_csv(app_name)
                            writer.writerow([
                                date,
                                app_name,
                                category,
                                seconds,
                                self.format_time(seconds)
                            ])
                    messagebox.showinfo("Экспорт завершен",f"Данные сохранены в {filename}\n\nРазделитель: {delimiter_var.get()}\nКодировка: {encoding_var.get()}")
                    settings_window.destroy()
                except Exception as ex:
                    be.log_error(f"Не удалось экспортировать данные.\n{ex}")
                    messagebox.showerror("Ошибка", f"Не удалось экспортировать данные.\n{ex}")
        ttk.Button(settings_window, text="Экспортировать", command=do_export).pack(pady=20)
        ttk.Button(settings_window, text="Отмена", command=settings_window.destroy).pack()

    def optimize_database(self):
        # Оптимизирует базу данных
        try:
            db.database_optimazer()
            messagebox.showinfo("Успех", "База данных оптимизирована.")
        except Exception as ex:
            messagebox.showerror("Ошибка", f"Не удалось оптимизировать базу данных.\n{ex}")
            be.log_error(f"Ошибка!\n{ex}")

    def start_new_session(self):
        # Начало новой сессии
        try:
            start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            session_id = db.insert_session(start_time)
            return session_id
        except Exception as ex:
            be.log_error(f"Ошибка!\n{ex}")
            return None

    def end_session(self, session_id, app_switches, idle_time):
        # Завершение сессии
        try:
            end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            total_activity = db.get_session_by_SESSION_ID_db(session_id)
            start_row = db.get_session_by_ID_db(session_id)
            if start_row:
                start_time = datetime.strptime(start_row[0], "%Y-%m-%d %H:%M:%S")
                end_time_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
                duration = int((end_time_dt - start_time).total_seconds())
            else:
                duration = 0
            db.update_session_db(end_time, duration, total_activity, idle_time, app_switches, session_id)
            logging.info(f"Сессия {session_id} завершена. Длительность: {duration} сек, активность: {total_activity} сек, переключений: {app_switches}")
        except Exception as ex:
            be.log_error(f"Ошибка!\n{ex}")

    def save_activity(self, app_name, category, duration, session_id):
        # Сохраняет запись об активности пользователя
        try:
            time = datetime.now().strftime("%Y-%m-%d")
            db.insert_activity_db(app_name, category, time, duration, session_id)
        except Exception as ex:
            be.log_error(f"Ошибка!\n{ex}")

    def monitor_activity(self):
        # Функция слежки за пользователем
        last_window = ""
        last_time = time.time()
        screenshot_counter = 0
        app_switches = 0
        idle_time_total = 0
        self.current_session = self.start_new_session()
        last_activity_time = time.time()
        logging.info("Слежка началась...")
        while self.running:
            try:
                current_time = time.time()
                if self.check_idle_time():
                    idle_duration = current_time - last_activity_time
                    idle_time_total += idle_duration
                    if self.current_session and idle_duration > self.idle_threshold:
                        self.end_session(self.current_session, app_switches, idle_time_total)
                        self.current_session = None
                        app_switches = 0
                        idle_time_total = 0
                    time.sleep(5)
                    continue
                if not self.current_session:
                    self.current_session = self.start_new_session()
                    last_activity_time = current_time
                    app_switches = 0
                    idle_time_total = 0
                last_activity_time = current_time
                current_window = self.get_active_window_title()
                current_time = time.time()
                if current_window != self.current_app:
                    self.current_app = current_window
                    self.current_app_start = current_time
                if current_window != last_window:
                    if last_window and last_window != "Неизвестно":
                        app_switches += 1
                        duration = int(current_time - last_time)
                        if duration > self.min_activity_time:
                            category = self.get_app_category(last_window)
                            self.save_activity(last_window, category, duration, self.current_session)
                            self.queue.put("update_stats")
                    last_window = current_window
                    last_time = current_time
                screenshot_counter += 1
                if screenshot_counter >= self.screenshot_interval:
                    self.take_screenshot(self.current_session)
                    screenshot_counter = 0
                time.sleep(1)
            except Exception as ex:
                be.log_error(f"Ошибка! Не удалось уследить за пользователем.\n{ex}")
                time.sleep(5)

    def take_screenshot(self, session_id):
        # Создаёт скриншот и сохраняет его
        try:
            screenshots_dir = "screenshots"
            if not os.path.exists(screenshots_dir):
                os.makedirs(screenshots_dir)
            filename = os.path.join(
                screenshots_dir,
                f"screenshot_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.png"
            )
            screenshot = ImageGrab.grab()
            screenshot.save(filename, 'PNG', optimize=True)
            time = datetime.now().isoformat()
            db.insert_screenshot_db(filename, time, session_id)
            logging.info(f"Скриншот сохранён как: {filename}")
        except Exception as ex:
            be.log_error(f"Ошибка!\n{ex}")

    def cleanup_old_screenshots(self, days_to_keep=7):
        # Удаляет скриншоты старше N дней
        try:
            screenshots_dir = "screenshots"
            if not os.path.exists(screenshots_dir):
                return
            current_time = time.time()
            deleted_count = 0
            for filename in os.listdir(screenshots_dir):
                filepath = os.path.join(screenshots_dir, filename)
                if os.path.isfile(filepath):
                    file_time = os.path.getmtime(filepath)
                    if (current_time - file_time) > days_to_keep * 86400:
                        os.remove(filepath)
                        deleted_count += 1
            if deleted_count > 0:
                logging.info(f"Старые скриншоты были очищены в количестве: {deleted_count}.")
        except Exception as ex:
            be.log_error(f"Ошибка! Не удалось очистить старые скриншоты.\n{ex}")

    def show_report(self, date_condition, title, limit=50):
        # Универсальный метод для отчетов
        try:
            for row in self.tree.get_children():
                self.tree.delete(row)
            rows = db.get_special_activity_db(date_condition, limit)
            for app_name, seconds, category in rows:
                display_time = self.format_time(seconds)
                category_name = self.get_category_name(category)
                icon = self.get_app_icon(app_name)
                self.tree.insert('', 'end', values=(f"{icon} {app_name}", display_time, category_name))
            self.root.title(f"Time Tracker - {title}")
            self.update_status(f"Отчёт {title.lower()} сформирован.")
        except Exception as ex:
            be.log_error(f"Ошибка!\n{ex}")

    def generate_report(self):
        self.show_report("date = date('now', '0 days')", "за сегодня", 100)

    def show_yesterday_report(self):
        self.show_report("date = date('now', '-1 days')", "за вчера", 100)

    def show_weekly_report(self):
        self.show_report("date >= date('now', '-7 days')", "за неделю", 500)

    def show_monthly_report(self):
        self.show_report("date >= date('now', '-30 days')", "за месяц", 1000)

    def load_settings(self):
        # Загрузка настроек из БД
        try:
            rows = db.get_settings_db()
            for key, value in rows:
                if key == 'screenshot_interval':
                    self.screenshot_interval = int(value)
                elif key == 'screenshot_delete_interval':
                    self.screenshot_delete_interval = int(value)
                elif key == 'min_activity_time':
                    self.min_activity_time = int(value)
                elif key == 'idle_threshold':
                    self.idle_threshold = int(value)
                elif key == 'notifications_enabled':
                    self.notifications_enabled = value.lower() == 'true'
                elif key == 'auto_backup_enabled':
                    self.auto_backup_enabled = value.lower() == 'true'
        except Exception as ex:
            pass

    def save_setting(self, key, value):
        # Сохранение настроек в БД
        try:
            db.insert_settings_db(key, value)
        except Exception as ex:
            pass

    def update_status(self, message):
        # Обновление текста в статус-баре
        self.status_label.config(text=message)

    def update_stats_status(self):
        # Обновление статистики в статус-баре
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            count, total = db.get_stats_status_by_DATE_db(today)
            if hasattr(self, 'current_session') and self.current_session:
                session = db.get_stats_status_by_ID_db(self.current_session)
                if session:
                    session_time = session[0] or 0
                    self.stats_status_label.config(
                        text=f"Сегодня: {self.format_time(total or 0)} | Сессия: {self.format_time(session_time)}"
                    )
                else:
                    self.stats_status_label.config(text=f"Сегодня: {self.format_time(total or 0)}")
            else:
                self.stats_status_label.config(text=f"Сегодня: {self.format_time(total or 0)}")
        except Exception as ex:
            pass

    def update_live_stats(self):
        # Обновление статистики в реальном времени
        try:
            app_icon = self.get_app_icon(self.current_app)
            self.current_app_label.config(text=f"Приложение: {app_icon} {self.current_app}")
            if self.current_app != "Unknown" and self.current_app != "Неизвестно":
                elapsed = int(time.time() - self.current_app_start)
                self.current_time_label.config(text=f"Время: {self.format_time(elapsed)}")
            if self.check_idle_time():
                self.idle_label.config(text="⚠️ Пользователь бездействует", foreground='orange')
            else:
                self.idle_label.config(text="")
            self.refresh_stats_view()
            self.update_stats_status()
        except Exception as ex:
            be.log_error(f"Ошибка! Не удалось обновить статистику в реальном времени.\n{ex}")
        self.root.after(1000, self.update_live_stats)

    def refresh_stats_view(self):
        # Обновление отображения статистики
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            total = db.get_stats_status_by_DATE_db(today, False)
            self.total_time_label.config(text=f"Всего времени: {self.format_time(total)}")
            rows = db.get_info_for_refresh_stats_view(today)
            category_totals = {row[0]: row[1] for row in rows}
            for category, label in self.category_labels.items():
                seconds = category_totals.get(category, 0)
                label.config(text=self.format_time(seconds))
            rows = db.get_info_for_refresh_stats_view(today, False)
            for i, (app_name, seconds) in enumerate(rows):
                if i < 10:
                    icon = self.get_app_icon(app_name)
                    display_name = app_name[:40] + "..." if len(app_name) > 40 else app_name
                    self.top_apps[i][0].config(text=f"{i + 1}. {icon} {display_name}")
                    self.top_apps[i][1].config(text=self.format_time(seconds))
            for i in range(len(rows), 10):
                self.top_apps[i][0].config(text=f"{i + 1}. ")
                self.top_apps[i][1].config(text="0 мин")
        except Exception as ex:
            be.log_error(f"Ошибка! Не удалось обновить отображение статистики.\n{ex}")

    def setup_tray(self):
        # Создание иконки в трее
        try:
            image = Image.new('RGB', (64, 64), color='#2E8B57')
            dc = ImageDraw.Draw(image)
            dc.rectangle((20, 20, 44, 44), fill='white')
            dc.text((10, 10), "TT", fill='white')

            def on_double_click(icon, item):
                self.show_window()

            def on_settings():
                self.show_window()
                self.open_settings()

            menu = pystray.Menu(
                pystray.MenuItem("Показать", self.show_window, default=True),
                pystray.MenuItem("Настройки", on_settings),
                pystray.MenuItem("Выход", self.quit_app)
            )
            self.tray_icon = pystray.Icon("time_tracker", image, "Time Tracker", menu)
            self.tray_icon.on_double_click = on_double_click
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as ex:
            be.log_error(f"Не удалось создать иконку в трее.\n{ex}")

    def process_queue(self):
        # Обработка сообщений из других потоков
        try:
            while True:
                msg = self.queue.get_nowait()
                if msg == "update_stats":
                    self.refresh_stats_view()
                    self.update_stats_status()
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)

    def check_idle_time(self):
        # Проверка на бездействие пользователя
        try:
            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
            ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
            idle_time = (ctypes.windll.kernel32.GetTickCount() - lii.dwTime) / 1000
            return idle_time > self.idle_threshold
        except:
            return False

    def get_active_window_title(self):
        # Получает заголовок активного окна
        try:
            window = gw.getActiveWindow()
            if window and window.title:
                return window.title
        except Exception as ex:
            be.log_error(f"Ошибка! Не удалось получить название окна.\n{ex}")
        return "Неизвестно"

    def get_category_name(self, category="other"):
        # Возвращение русского названия категории
        names = {
            'browser': 'Браузеры',
            'editor': 'Редакторы',
            'office': 'Офис',
            'communication': 'Общение',
            'media': 'Медиа',
            'game': 'Игры',
            'system': 'Системное',
            'development': 'Разработка',
            'other': 'Другое'
        }
        return names.get(category, category)

    def get_app_category(self, app_name):
        # Определение категории приложения
        app_name_lower = app_name.lower()
        categories = {
            'browser': ['chrome', 'firefox', 'opera', 'edge', 'browser', 'yandex', 'браузер'],
            'editor': ['code', 'studio', 'sublime', 'notepad', 'pycharm', 'visual', 'vim', 'pycharm64'],
            'office': ['word', 'excel', 'powerpoint', 'outlook', 'office', 'document', 'документ'],
            'communication': ['telegram', 'whatsapp', 'discord', 'skype', 'zoom', 'slack', 'viber'],
            'media': ['spotify', 'vlc', 'media', 'player', 'music', 'video', 'youtube', 'кинопоиск'],
            'game': ['factorio', 'game', 'игра', 'steam', 'epic', 'warcraft', 'dota', 'counter-strike'],
            'system': ['диспетчер задач', 'task manager', 'explorer', 'проводник', 'system', 'sys'],
            'development': ['pycharm', 'pycharm64', 'pycharm community edition', 'pycharm ce', 'idea', 'webstorm',
                            'phpstorm']
        }
        for category, keywords in categories.items():
            if any(keyword in app_name_lower for keyword in keywords):
                return category
        return 'other'

    def get_app_icon(self, app_name):
        # Возвращает иконку для приложения
        icons = {
            'Chrome': '🌐',
            'Yandex': 'Я',
            'Word': '📝',
            'Excel': '📊',
            'PowerPoint': '📽️',
            'VS Code': '💻',
            'PyCharm': '🐍',
            'Telegram': '✈️',
            'Discord': '🎮',
            'Spotify': '🎵',
            'Factorio': '⚙️',
            'Steam': '🎮',
            'Zoom': '📹',
            'Skype': '📞'
        }
        for key, icon in icons.items():
            if key.lower() in app_name.lower():
                return icon
        return '📌'

    def format_time(self, seconds):
        # Форматирование времени
        if not seconds:
            return "0 сек"
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds_remain = divmod(remainder, 60)
        if hours:
            return f"{hours} ч {minutes} мин"
        elif minutes:
            return f"{minutes} мин {seconds_remain} сек"
        else:
            return f"{seconds_remain} сек"

    def show_window(self):
        # Показать главное окно
        self.root.after(0, self.root.deiconify)
        self.root.after(0, self.root.lift)
        self.root.after(0, self.root.focus_force)

    def hide_window(self):
        # Скрыть окно в трей
        self.root.withdraw()

    def quit_app(self):
        # Выход из приложения
        self.running = False
        if hasattr(self, 'current_session') and self.current_session:
            self.end_session(self.current_session, 0, 0)
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        self.root.quit()
        sys.exit(0)

    def run(self):
        # Запуск tkinter
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.quit_app()

if __name__ == "__main__":
    app = TimeTrackerApp()
    app.run()