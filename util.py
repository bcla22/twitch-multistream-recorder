import json
import logging
import os

from config import Setting

logger = logging.getLogger(__name__)
SETTINGS_PATH = os.path.join(os.getcwd(), 'conf', 'settings.json')


def get_settings() -> dict[str]:
    """
    Return dict from settings.json
    """
    if not os.path.isfile(SETTINGS_PATH):
        with open(SETTINGS_PATH, 'w') as f:
            f.write(json.dumps({}))

    with open(SETTINGS_PATH, 'r') as f:
        return json.loads(f.read())


def get_setting(key: Setting):
    """
    Return the value of a single setting, or None
    """
    settings = get_settings()
    if not key.value in settings.keys():
        return None
    return settings[key.value]


def update_settings(new_settings: dict[str]) -> dict[str]:
    """
    Update settings.json with values from dict
    """
    settings = get_settings()
    for k, v in new_settings.items():
        logger.info(f"Updating setting {k} to {v}")
        settings[k] = v

    with open(SETTINGS_PATH, 'w') as f:
        f.write(json.dumps(settings))

    return get_settings()


def file_size_mb(path: str) -> float:
    """
    Get the size of a file in mb
    """
    stats = os.stat(path)
    return stats.st_size / (1024 * 1024)
