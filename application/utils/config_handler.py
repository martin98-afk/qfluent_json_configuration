import json
import os
import configparser
from collections import defaultdict

from loguru import logger
from ruamel.yaml import YAML
from datetime import datetime

from application.utils.utils import error_catcher_decorator

yaml = YAML()
PATH_PREFIX = './configurations/'
FILE_FILTER = "JSON 文件 (*.json);;YAML 文件 (*.yaml *.yml);;INI 文件 (*.ini)"
os.makedirs(PATH_PREFIX, exist_ok=True)
HISTORY_PATH = os.path.expanduser(os.path.join(PATH_PREFIX, "历史版本记录.json"))


def path_exists(path):
    return os.path.exists(os.path.join(PATH_PREFIX, path))

@error_catcher_decorator
def load_config(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        if file_path.endswith('.json'):
            return json.load(file)
        elif file_path.endswith('.yaml') or file_path.endswith('.yml'):
            return yaml.load(file)
        elif file_path.endswith('.ini'):
            config = configparser.ConfigParser()
            config.read_file(file)
            return {section: dict(config[section]) for section in config.sections()}
        else:
            raise ValueError(f"Unsupported file format: {file_path}")

@error_catcher_decorator
def save_config(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as file:
        if file_path.endswith('.json'):
            json.dump(data, file, ensure_ascii=False, indent=4)
        elif file_path.endswith('.yaml') or file_path.endswith('.yml'):
            yaml.dump(data, file)
        elif file_path.endswith('.ini'):
            config = configparser.ConfigParser()
            for section, values in data.items():
                if isinstance(values, str) and len(values) == 0:
                    values = {}
                elif isinstance(values, str):
                    values = {section: values}
                config[section] = values
            config.write(file)
        else:
            raise ValueError(f"Unsupported file format: {file_path}")

def load_history():
    history = defaultdict(list)
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            try:
                history_data = json.load(f)
                if isinstance(history_data, list):
                    for data in history_data:
                        history[data[0]].append(
                            {
                                "file_type": "json",
                                "save_time": data[1],
                                "history_data": data[2]
                            }
                        )
                else:
                    history = history | history_data
            except:
                pass
    # 按版本时间排序
    history = {k: sorted(v, key=lambda x: x["save_time"], reverse=True) for k, v in history.items()}
    return history


def save_history(path, config):
    history = defaultdict(list)
    file_name = ".".join(os.path.basename(path).split(".")[:-1])
    file_type = os.path.basename(path).split(".")[-1]
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            try:
                history_data = json.load(f)
                if isinstance(history_data, list):
                    for data in history_data:
                        history[data[0]].append(
                            {
                                "file_type": "json",
                                "save_time": data[1],
                                "history_data": data[2]
                            }
                        )
                else:
                    history = history | history_data
            except:
                pass

    history[file_name].append(
        {
            "file_type": file_type,
            "save_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "history_data": config
        }
    )

    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
