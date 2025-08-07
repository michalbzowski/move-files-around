import os
import json
import numpy as np
import face_recognition
from sklearn.cluster import DBSCAN, HDBSCAN


def cluster_faces_in_directory(directory, notify):
    # Tu przechowujemy wektory twarzy i meta info
    face_encodings = []
    face_metadata = []  # (filename, face_index)

    # 1. Wczytanie i enkodowanie twarzy
    listdir = os.listdir(directory)
    total_steps = len(listdir)
    p = 0
    for filename in listdir:
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            path = os.path.join(directory, filename)
            image = face_recognition.load_image_file(path)
            encodings = face_recognition.face_encodings(image)
            for i, encoding in enumerate(encodings):
                face_encodings.append(encoding)
                face_metadata.append({'filename': filename, 'face_index': i})
        p += 1
        progress = int(p / total_steps * 100)
        notify(progress)

    if not face_encodings:
        return {}

    X = np.array(face_encodings)

    # 2. Klasteryzacja
    clustering = HDBSCAN( min_samples=1, metric='cosine').fit(X)
    labels = clustering.labels_

    # 3. Przypisz etykiety
    label_map = {}
    person_counter = 1
    for label in set(labels):
        if label == -1:
            continue
        label_map[label] = f"Osoba {person_counter}"
        person_counter += 1

    # 4. Wynik: mapa plików do list osób z twarzami
    file_to_faces = {}
    for idx, label in enumerate(labels):
        filename = face_metadata[idx]['filename']
        if filename not in file_to_faces:
            file_to_faces[filename] = []
        if label == -1:
            tag = "Nieznany"
        else:
            tag = label_map[label]
        if tag not in file_to_faces[filename]:
            file_to_faces[filename].append(tag)

    return file_to_faces


# Funkcja do zapisu/odczytu do pliku JSON (opcjonalnie)
def save_image_tags(tags_map, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(tags_map, f, ensure_ascii=False, indent=2)


def load_image_tags(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}
