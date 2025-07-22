import sqlite3
import threading
from contextlib import contextmanager

class Database:
    """
    Простіший обгортковий клас для роботи з SQLite з довгоживим підключенням.
    Підтримує паралельні запити завдяки check_same_thread=False.

    Налаштування PRAGMA для оптимізації продуктивності:
      - journal_mode=WAL для кращої конкурентності
      - synchronous=NORMAL для балансування надійності та швидкості
      - temp_store=MEMORY для роботи з тимчасовими таблицями в пам’яті
      - cache_size=-2000 для збільшення кешу до ~2MB
    """
    def __init__(self, path: str):
        self.path = path
        # Створюємо довгоживе підключення
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        # Налаштовуємо PRAGMA
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute("PRAGMA temp_store = MEMORY;")
        self._conn.execute("PRAGMA cache_size = -2000;")
        # Блокування для безпечного доступу з декількох потоків
        self._lock = threading.Lock()

    def close(self) -> None:
        """
        Закриває з’єднання з базою даних.
        """
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    @contextmanager
    def transaction(self):
        """
        Контекст для транзакцій. Виконує commit після успіху або rollback при виключенні.
        """
        with self._lock:
            try:
                yield
                self._conn.commit()
            except:
                self._conn.rollback()
                raise

    def query(self, sql: str, params: tuple = ()) -> list:
        """
        Виконує SELECT-запит і повертає всі рядки.
        """
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.fetchall()

    def execute(self, sql: str, params: tuple = ()) -> int:
        """
        Виконує INSERT/UPDATE/DELETE і повертає lastrowid.
        """
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur.lastrowid

    def executemany(self, sql: str, seq_of_params: list) -> int:
        """
        Виконує багаторазові операції (bulk INSERT/UPDATE) та повертає кількість оброблених рядків.
        """
        with self._lock:
            cur = self._conn.executemany(sql, seq_of_params)
            self._conn.commit()
            return cur.rowcount

    def __del__(self):
        # Гарантуємо закриття при знищенні об'єкта
        self.close()
