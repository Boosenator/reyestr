# modules/settings.py

import json
from pathlib import Path
from config import PROJECT_ROOT

SETTINGS_FILE = PROJECT_ROOT / "config" / "settings.json"

class SettingsManager:
    def __init__(self):
        self.filepath = SETTINGS_FILE
        self._data = {"folders": [], "active": None}
        self.load()

    def load(self):
        if self.filepath.exists():
            with open(self.filepath, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        else:
            self.save()

    def save(self):
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get_folders(self):
        return list(self._data["folders"])

    def add_folder(self, path):
        if path in self._data["folders"]:
            return False
        self._data["folders"].append(path)
        if not self._data["active"]:
            self._data["active"] = path
        self.save()
        return True

    def remove_folder(self, path):
        if path in self._data["folders"]:
            self._data["folders"].remove(path)
            if self._data["active"] == path:
                self._data["active"] = self._data["folders"][0] if self._data["folders"] else None
            self.save()

    def get_active(self):
        return self._data.get("active")

    def set_active(self, path):
        if path in self._data["folders"]:
            self._data["active"] = path
            self.save()
