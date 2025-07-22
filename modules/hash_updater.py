import concurrent.futures
from modules.database import db, propagate_metadata_for_hash
from modules.utils import compute_file_hash


def background_hash_updates(max_workers=4):
    """
    Фонове обчислення SHA-256 хешів для нових записів і синхронізація метаданих дублікатів.
    max_workers – кількість потоків для паралельної обробки.
    """
    # Отримуємо всі записи без file_hash
    rows = db.query("SELECT id, filepath FROM documents WHERE file_hash IS NULL")

    def worker(row):
        doc_id, path = row
        try:
            # Обчислюємо хеш файлу
            fh = compute_file_hash(path)
            # Оновлюємо поле file_hash
            db.execute("UPDATE documents SET file_hash=? WHERE id=?", (fh, doc_id))
            # Синхронізуємо метадані дублікатів за хешем
            propagate_metadata_for_hash(fh, doc_id)
        except Exception:
            # Ігноруємо помилки I/O або відсутності файлу
            pass

    # Паралельна обробка у потоках
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(worker, rows)
