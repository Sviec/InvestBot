import json


def get_path(path: str):
    with open("app/data/menu/ru.json", "r", encoding="utf-8") as f:
        menu_data = json.load(f)

    path_parts = path.split('%')
    current_level = menu_data

    for part in path_parts:
        if part in current_level:
            current_level = current_level[part]
        elif 'buttons' in current_level:
            try:
                current_level = current_level['buttons'][part]
            except KeyError:
                continue
        else:
            return None
    return current_level
