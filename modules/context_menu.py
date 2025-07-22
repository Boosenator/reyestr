# modules/context_menu.py

import os
import subprocess
import tkinter as tk
from tkinter import simpledialog, messagebox
from .utils import rename_file, delete_file
from .edit_window import EditWindow
from .links_window import LinksWindow
from .database import db, get_linked_count

# === Дії над документом ===

def _get_doc_id(app):
    """
    Повертає doc_id як int або None.
    """
    doc_id = app.selected_id
    try:
        return int(doc_id)
    except (TypeError, ValueError):
        return None


def open_selected(app):
    doc_id = _get_doc_id(app)
    if doc_id is None:
        return
    rows = db.query(
        "SELECT filepath FROM documents WHERE id=?", (doc_id,)
    )
    if rows and os.path.exists(rows[0][0]):
        os.startfile(rows[0][0])


def show_in_folder(app):
    doc_id = _get_doc_id(app)
    if doc_id is None:
        return
    rows = db.query(
        "SELECT filepath FROM documents WHERE id=?", (doc_id,)
    )
    if rows and os.path.exists(rows[0][0]):
        subprocess.Popen(f'explorer /select,"{rows[0][0]}"')


def rename_selected(app):
    doc_id = _get_doc_id(app)
    if doc_id is None:
        return
    rows = db.query(
        "SELECT filename, filepath FROM documents WHERE id=?", (doc_id,)
    )
    if not rows:
        return
    filename, filepath = rows[0]
    base, ext = os.path.splitext(filename)
    new_base = simpledialog.askstring("Перейменування", "Нова назва:", initialvalue=base)
    if not new_base:
        return
    try:
        new_filename = new_base + ext
        new_path = rename_file(filepath, new_filename)
        db.execute(
            "UPDATE documents SET filename=?, filepath=? WHERE id=?",
            (new_filename, new_path, doc_id)
        )
        app.load_registry_data()
    except Exception as e:
        messagebox.showerror("Помилка", str(e))


def delete_selected(app):
    doc_id = _get_doc_id(app)
    if doc_id is None:
        return
    if not messagebox.askyesno("Підтвердження", "Видалити файл?"):
        return
    rows = db.query(
        "SELECT filepath FROM documents WHERE id=?", (doc_id,)
    )
    db.execute(
        "DELETE FROM documents WHERE id=?", (doc_id,)
    )
    if rows:
        delete_file(rows[0][0])
    app.load_registry_data()


def edit_selected(app):
    doc_id = _get_doc_id(app)
    if doc_id is not None:
        EditWindow(app, doc_id)


def show_links_window(app):
    doc_id = _get_doc_id(app)
    if doc_id is not None:
        LinksWindow(app, doc_id)

# === Контекстне меню ===

def build_context_menu(app, tree=None):
    menu = tk.Menu(app, tearoff=0)

    actions = [
        ("📄 Відкрити документ",    open_selected),
        ("📁 Показати в папці",     show_in_folder),
        ("✂️ Перейменувати",        rename_selected),
        ("✏️ Редагувати",           edit_selected),
        ("🗑️ Видалити",            delete_selected),
    ]

    for label, fn in actions:
        menu.add_command(label=label, command=lambda f=fn: f(app))

    menu.add_separator()

    try:
        cnt = get_linked_count(_get_doc_id(app))
    except:
        cnt = 0
    menu.add_command(
        label=f"🔗 Зв’язки з документами ({cnt})",
        command=lambda: show_links_window(app)
    )

    return menu
