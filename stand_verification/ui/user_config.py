"""
Сохранение последних настроек подключения.

Файл `config.json` лежит рядом с exe (или рядом с gui_stand.py).
"""

import json
import os


CONFIG_FILENAME = "config.json"


def _config_path():
    """Путь к config.json — рядом с exe или с корнем проекта."""
    import sys
    if getattr(sys, 'frozen', False):
        # exe-сборка
        base = os.path.dirname(sys.executable)
    else:
        # python gui_stand.py — корень проекта
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, CONFIG_FILENAME)


def load_config():
    """Загрузить настройки. Пустой dict при ошибке."""
    path = _config_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(config):
    """Сохранить настройки."""
    path = _config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception:
        pass