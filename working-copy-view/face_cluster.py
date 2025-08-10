import os
import json


# Funkcja do zapisu/odczytu do pliku JSON (opcjonalnie)
def save_image_tags(tags_map, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(tags_map, f, ensure_ascii=False, indent=2)


def load_image_tags(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}
