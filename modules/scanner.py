import os
import sqlite3
from config import DOCUMENTS_DIR, DB_PATH
from .database import get_existing_filepaths, insert_documents_batch

def batch_scan(folder_path: str, batch_size: int) -> None:
    """Scan folder_path and insert file metadata in batches."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        batch = []
        for root, _, files in os.walk(folder_path):
            for name in files:
                path = os.path.join(root, name)
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                rel = os.path.relpath(root, folder_path)
                batch.append((name, path, '' if rel == '.' else rel, st.st_mtime, None))
                if len(batch) >= batch_size:
                    conn.execute("BEGIN")
                    cur.executemany(
                        "INSERT INTO documents (filename, filepath, folder, last_modified, file_hash, is_new) "
                        "VALUES (?,?,?,?,?,1)",
                        batch,
                    )
                    conn.commit()
                    batch.clear()
        if batch:
            conn.execute("BEGIN")
            cur.executemany(
                "INSERT INTO documents (filename, filepath, folder, last_modified, file_hash, is_new) "
                "VALUES (?,?,?,?,?,1)",
                batch,
            )
            conn.commit()
    finally:
        cur.close()
        conn.close()

def insert_new_files(base_dir: str = None,
                     progress_callback=None,
                     batch_size: int = 500,
                     throttle: int = 1):
    """
    Швидке сканування директорії base_dir з використанням os.walk та батчеві вставки без обчислення хешу.

    :param base_dir: коренева директорія для сканування (за замовчуванням DOCUMENTS_DIR)
    :param progress_callback: функція progress_callback(done, total)
    :param batch_size: розмір батчу для вставки в БД
    :param throttle: інтервал оновлення прогресу
    """
    if base_dir is None:
        base_dir = DOCUMENTS_DIR

    print(f"[scan] Starting new file scan in: {base_dir}")

    # Існуючі шляхи в БД
    existing_paths = set(get_existing_filepaths())
    print(f"[scan] Retrieved {len(existing_paths)} existing file paths from DB")

    # Збираємо список усіх файлів для сканування
    all_files = []
    for root, _, files in os.walk(base_dir):
        print(f"[scan] Entering directory: {root}")
        for f in files:
            all_files.append(os.path.join(root, f))
    total = len(all_files)
    print(f"[scan] Found {total} files to scan")

    # Початкове оновлення прогресу: 0 файлів із total
    if progress_callback:
        print(f"[scan] Progress: 0/{total}")
        progress_callback(0, total)

    done = 0
    new_records = []

    for full_path in all_files:
        done += 1

        # Періодичне оновлення прогресу
        if progress_callback and done % throttle == 0:
            print(f"[scan] Progress: {done}/{total}")
            progress_callback(done, total)

        # Пропускаємо вже наявні
        if full_path in existing_paths:
            continue

        # Пробуємо отримати дату модифікації
        try:
            last_mod = os.path.getmtime(full_path)
        except OSError as e:
            print(f"[scan] Skipping unreadable file: {full_path} ({e})")
            continue

        rel_folder = os.path.relpath(os.path.dirname(full_path), base_dir)
        if rel_folder == '.':
            rel_folder = ''
        filename = os.path.basename(full_path)
        new_records.append((filename, full_path, rel_folder, last_mod, None))

        # Батчевий запис у БД
        if len(new_records) >= batch_size:
            print(f"[scan] Inserting batch of {len(new_records)} records into DB")
            insert_documents_batch(new_records)
            new_records.clear()

    # Вставляємо залишки
    if new_records:
        print(f"[scan] Inserting final batch of {len(new_records)} records into DB")
        insert_documents_batch(new_records)

    # Остаточне оновлення прогресу
    if progress_callback:
        print(f"[scan] Progress: {done}/{total} (complete)")
        progress_callback(done, total)

    print(f"[scan] Scan complete. Processed {done} files")
