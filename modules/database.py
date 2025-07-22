from modules.db import Database
from config import DB_PATH, TABLES, INITIAL_DOCUMENT_TYPES, REVERSE_LINKS

# Ініціалізуємо обгортку для доступу до БД
# Єдине довгоживе підключення та оптимізовані PRAGMA налаштування в Database
db = Database(DB_PATH)


def init_db():
    """
    Створює всі необхідні таблиці та індекси за описом у TABLES,
    проводить міграцію для file_hash та налаштовує PRAGMA для продуктивності.
    """
    # Виконуємо всі DDL та міграції в рамках транзакції
    with db.transaction():
        cur = db._conn.cursor()
        # Налаштування WAL та синхронізації (PRAGMA задаються при ініціалізації db)
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")

        # Створення/міграція таблиць та індексів
        for name, info in TABLES.items():
            # Створити таблицю, якщо відсутня
            cur.execute(f"CREATE TABLE IF NOT EXISTS {name} ({info['columns']})")

            # Для documents забезпечити колонку file_hash
            if name == 'documents':
                cols = [row[1] for row in cur.execute("PRAGMA table_info(documents)").fetchall()]
                if 'file_hash' not in cols:
                    cur.execute("ALTER TABLE documents ADD COLUMN file_hash TEXT")

            # Створити індекси
            for idx_name, col in info.get('indices', []):
                cur.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {name}({col})")


def populate_initial_types():
    """
    Вставляє початкові типи документів та категорії з INITIAL_DOCUMENT_TYPES.
    """
    db.executemany(
        "INSERT OR IGNORE INTO document_types (type_name, category) VALUES (?, ?)",
        INITIAL_DOCUMENT_TYPES
    )


def clear_documents():
    db.execute("DELETE FROM document_numbers")
    db.execute("DELETE FROM documents")


def get_existing_filepaths():
    rows = db.query("SELECT filepath FROM documents")
    return [r[0] for r in rows]


def insert_document(filename, filepath, folder, last_modified, file_hash=None):
    return db.execute(
        "INSERT INTO documents (filename, filepath, folder, last_modified, file_hash, is_new) VALUES (?,?,?,?,?,1)",
        (filename, filepath, folder, last_modified, file_hash)
    )


def insert_documents_batch(records):
    """
    Батчеві вставки для швидшого сканування.
    records: list of tuples (filename, filepath, folder, last_modified, file_hash)
    """
    return db.executemany(
        "INSERT INTO documents (filename, filepath, folder, last_modified, file_hash, is_new) VALUES (?,?,?,?,?,1)",
        records
    )


def propagate_metadata_for_hash(file_hash, new_id):
    """
    Синхронізує поля метаданих між дублікатами файлів за хешем.
    """
    fields = [
        'doc_type','doc_number','doc_date','sender',
        'status','tags','description','is_controlled','deadline'
    ]
    new_vals = db.query(
        f"SELECT {','.join(fields)} FROM documents WHERE id=?", (new_id,)
    )[0]
    if any(new_vals):
        sets = ','.join(f"{f}=?" for f in fields)
        db.execute(
            f"UPDATE documents SET {sets} WHERE file_hash=? AND id!=?",
            (*new_vals, file_hash, new_id)
        )
    else:
        rows = db.query(
            f"SELECT id,{','.join(fields)} FROM documents WHERE file_hash=? AND id!=?", (file_hash, new_id)
        )
        for rid, *old_vals in rows:
            if any(old_vals):
                sets = ','.join(f"{f}=?" for f in fields)
                db.execute(
                    f"UPDATE documents SET {sets} WHERE id=?",
                    (*old_vals, rid)
                )
                break


def get_new_files_count():
    row = db.query("SELECT COUNT(*) FROM documents WHERE is_new=1")
    return row[0][0] if row else 0


def get_new_file_ids():
    rows = db.query("SELECT id FROM documents WHERE is_new=1")
    return [r[0] for r in rows]


def mark_all_as_old():
    db.execute("UPDATE documents SET is_new=0 WHERE is_new=1")


def get_document_numbers(doc_id):
    return db.query(
        "SELECT number_type, number_value FROM document_numbers WHERE document_id=?", (doc_id,)
    )


def save_document_numbers(doc_id, numbers):
    db.execute("DELETE FROM document_numbers WHERE document_id=?", (doc_id,))
    params = [(doc_id, t, v) for t, v in numbers]
    db.executemany(
        "INSERT INTO document_numbers (document_id, number_type, number_value) VALUES (?,?,?)",
        params
    )


def get_linked_count(doc_id):
    row = db.query(
        """
        SELECT COUNT(*) FROM (
            SELECT to_doc_id AS other_id FROM document_links WHERE from_doc_id=? AND to_doc_id!=?
            UNION
            SELECT from_doc_id AS other_id FROM document_links WHERE to_doc_id=? AND from_doc_id!=?
        ) sub
        """, (doc_id, doc_id, doc_id, doc_id)
    )
    return row[0][0] if row else 0


def get_linked_docs(doc_id):
    direct = db.query(
        "SELECT to_doc_id, link_type FROM document_links WHERE from_doc_id=?", (doc_id,)
    )
    rev_raw = db.query(
        "SELECT from_doc_id, link_type FROM document_links WHERE to_doc_id=?", (doc_id,)
    )
    reverse = [(other, REVERSE_LINKS.get(lt, lt)) for other, lt in rev_raw]
    seen = set()
    results = []
    for other_id, lt in direct + reverse:
        if other_id not in seen:
            seen.add(other_id)
            fn = db.query("SELECT filename FROM documents WHERE id=?", (other_id,))[0][0]
            results.append((other_id, fn, lt))
    return results