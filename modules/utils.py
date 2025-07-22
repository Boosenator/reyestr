import os
import subprocess
import sys
import hashlib

def open_folder(filepath):
    """
    Відкриває папку, в якій знаходиться файл, в залежності від ОС.
    """
    folder = os.path.dirname(filepath)
    if sys.platform == "win32":
        subprocess.Popen(f'explorer "{folder}"')
    elif sys.platform == "darwin":
        subprocess.call(["open", folder])
    else:
        subprocess.call(["xdg-open", folder])


def rename_file(old_path, new_name):
    """
    Перейменовує файл в тій же директорії і повертає новий шлях.
    """
    new_path = os.path.join(os.path.dirname(old_path), new_name)
    os.rename(old_path, new_path)
    return new_path


def delete_file(filepath):
    """
    Видаляє файл, якщо він існує.
    """
    if os.path.exists(filepath):
        os.remove(filepath)


def compute_file_hash(path, chunk_size=8192):
    """
    Обчислює SHA-256 хеш вмісту файлу та повертає його у вигляді шістнадцяткового рядка.
    """
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b''):
            h.update(chunk)
    return h.hexdigest()