import os
from math import ceil

from flask import Flask, render_template, request, jsonify, send_file, abort
from datetime import datetime
from werkzeug.utils import secure_filename
import shutil
from flask_socketio import SocketIO
from PIL import Image
import torch
import clip  # https://github.com/openai/CLIP

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'  # potrzebne do sesji, itp.
socketio = SocketIO(app, mode="rw", cors_allowed_origins=["http://localhost:5001", "http://127.0.0.1:5001"])

WORKING_COPY_DIR = os.getenv("WORKING_COPY_DIR", "../directories/test_dir/working_copy")
BIN_DIR = os.getenv("BIN_DIR", "../directories/test_dir/bin")
ALL_MEDIA_DIR = os.getenv("ALL_MEDIA_DIR", "../directories/test_dir/all_media")
THUMBNAILS_DIR = os.path.join(os.getcwd(), 'thumbnails')

# Lokalizacja pliku z zapisanymi tagami (np. w katalogu thumbnails lub innym)
IMAGE_TAGS_PATH = os.path.join('image_tags', 'image_tags.json')


# Funkcja do zapisu/odczytu do pliku JSON (opcjonalnie)
def save_image_tags(tags_map, path):
    with open(path, 'w', encoding='utf-8') as f:
        import json
        json.dump(tags_map, f, ensure_ascii=False, indent=2)



def load_image_tags(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            import json
            return json.load(f)
    return {}


# Przed obsługą endpointu lub na żądanie ładujesz tagi
image_tags_map = load_image_tags(IMAGE_TAGS_PATH)

# websocket clients
connected_clients = {}


def get_file_type(filename):
    ext = filename.lower().rsplit('.', 1)[-1]
    if ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']:
        return 'image'
    elif ext in ['mp4', 'webm', 'mov', 'avi', 'mkv']:
        return 'video'
    elif ext == 'pdf':
        return 'pdf'
    elif ext in ['txt', 'log', 'csv', 'json', 'md']:
        return 'text'
    else:
        return 'other'


def get_file_preview(filename, max_chars=300):
    import os
    path = os.path.join(WORKING_COPY_DIR, filename)
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(max_chars)
            # Zamiana nowych linii na HTML safe
            content = content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            return content
    except Exception:
        return '[Podgląd niedostępny]'


# Rejestracja w Jinja2
app.jinja_env.globals.update(get_file_preview=get_file_preview)


def format_bytes(value):
    if not isinstance(value, (int, float)):
        return value
    if value < 1024:
        return f"{value} B"
    elif value < 1024 ** 2:
        return f"{value / 1024:.1f} KB"
    else:
        return f"{value / (1024 ** 2):.2f} MB"


app.jinja_env.filters['format_bytes'] = format_bytes

import json


def get_thumb_path(size, filename):
    fname = secure_filename(filename)
    return os.path.join(THUMBNAILS_DIR, f"{size}_{fname}")


def generate_image_thumb(orig_path, thumb_path, size):
    with Image.open(orig_path) as im:
        im.thumbnail(size)
        os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
        im.save(thumb_path, "JPEG")


def allowed_image(filename):
    ext = filename.lower().rsplit('.', 1)[-1]
    return ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']


def allowed_pdf(filename):
    ext = filename.lower().rsplit('.', 1)[-1]
    return ext == 'pdf'


def serve_thumbnail(size, filename):
    width, height = map(int, size.split('x'))
    orig_path = os.path.join(WORKING_COPY_DIR, filename)
    thumb_path = get_thumb_path(size, filename)

    # Jeśli już jest wygenerowana miniatura
    if os.path.exists(thumb_path):
        return send_file(thumb_path, mimetype="image/jpeg")

    # Dla obrazów
    if allowed_image(filename) and os.path.exists(orig_path):
        try:
            generate_image_thumb(orig_path, thumb_path, (width, height))
            return send_file(thumb_path, mimetype="image/jpeg")
        except Exception as e:
            print(e)
            abort(500)
    # Dla PDF – generowanie miniatury PDF (pierwsza strona)
    if allowed_pdf(filename) and os.path.exists(orig_path):
        try:
            # Dopisz: pip install pdf2image poppler-utils
            from pdf2image import convert_from_path
            pages = convert_from_path(orig_path, first_page=1, last_page=1, size=(width, height))
            if pages:
                os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
                pages[0].save(thumb_path, "JPEG")
                return send_file(thumb_path, mimetype="image/jpeg")
        except Exception as e:
            print(e)
            abort(500)
    # Brak obsługiwanego typu
    abort(404)


@app.route('/thumb/<size>/<filename>')
def thumbnail(size, filename):
    return serve_thumbnail(size, filename)


@app.route('/')
def index():
    name = request.args.get('name', '').lower()
    filter_ext = [e.lower() for e in request.args.getlist('ext') if e]
    image_tags_filter = [p for p in request.args.getlist('image_tags') if p]  # nowy filtr tagów obrazków

    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))

    all_files = []
    extensions_set = set()
    has_no_ext = False

    # Pobierz listę unikalnych
    unique_image_tags = set()
    for p_list in image_tags_map.values():
        unique_image_tags.add(p_list['category'])
    unique_image_tags = sorted(unique_image_tags)

    for f in os.listdir(WORKING_COPY_DIR):
        full = os.path.join(WORKING_COPY_DIR, f)
        if os.path.isfile(full):
            filename_lower = f.lower()
            if '.' in f:
                ext = filename_lower.rsplit('.', 1)[-1]
                extensions_set.add(ext)
            else:
                has_no_ext = True

            # Filtracja po nazwie - jeśli wpisałeś
            if name and name not in filename_lower:
                continue

            # Filtracja po rozszerzeniu (multiselect)
            file_ext = filename_lower.rsplit('.', 1)[-1] if '.' in filename_lower else ''
            if filter_ext:
                # Jeśli plik bez rozszerzenia i filter_ext zawiera "no_ext", to pokazujemy
                if (file_ext == '' and 'no_ext' not in filter_ext) or (file_ext != '' and file_ext not in filter_ext):
                    continue

            # Filtr tagów

            if image_tags_filter:
                image_tags_attributes = image_tags_map.get(full)
                if image_tags_attributes is None:
                    continue
                if image_tags_attributes:
                    cat = image_tags_attributes['category']
                    if cat != image_tags_filter[0]:
                        continue

            stat = os.stat(full)

            all_files.append({
                'name': f,
                'size': stat.st_size,
                'date': datetime.fromtimestamp(stat.st_mtime),
                'type': get_file_type(f),
                'image_tags': []
            })

    total_files = len(all_files)
    total_pages = ceil(total_files / per_page)

    # Wycinanie „strony” z listy plików
    start = (page - 1) * per_page
    end = start + per_page
    files = all_files[start:end]

    # Przekaż do template: files, page, total_pages, per_page i inne dane
    # Przekaż rozszerzenia jako lista i flagę czy są pliki bez rozszerzenia
    extensions_list = sorted(extensions_set)
    return render_template('index.html',
                           files=files,
                           filter_name=name,
                           filter_ext=filter_ext,
                           extensions_list=extensions_list,
                           has_no_ext=has_no_ext,
                           total_files=len(all_files),
                           total_size=sum(f['size'] for f in all_files),
                           page=page,
                           total_pages=total_pages,
                           per_page=per_page,
                           unique_image_tags=unique_image_tags,
                           filter_image_tags=image_tags_filter)


@app.route('/api/files')
def list_files():
    ext = request.args.get('ext')
    name = request.args.get('name')
    files = []
    for f in os.listdir(WORKING_COPY_DIR):
        full = os.path.join(WORKING_COPY_DIR, f)
        if os.path.isfile(full):
            if ext and not f.lower().endswith(f'.{ext.lower()}'):
                continue
            if name and name.lower() not in f.lower():
                continue
            stat = os.stat(full)
            files.append({
                'name': f,
                'size': stat.st_size,
                'date': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'type': get_file_type(f)
            })
    # sortowanie po nazwie
    files_sorted = sorted(files, key=lambda x: x['name'].lower())
    return jsonify(files_sorted)


@app.route('/files/<filename>')
def serve_file(filename):
    # Pliki oryginalne – do pobierania lub otwierania
    file_path = os.path.join(WORKING_COPY_DIR, filename)
    if os.path.exists(file_path):
        return send_file(file_path)
    abort(404)


@app.route('/api/move', methods=['POST'])
def move_files():
    data = request.json
    dest = data.get('dest')
    files = data.get('files', [])
    if dest not in ['bin', 'AllMedia']:
        return jsonify({'error': 'invalid destination'}), 400
    dest_dir = BIN_DIR if dest == 'bin' else ALL_MEDIA_DIR
    os.makedirs(dest_dir, exist_ok=True)
    moved = []
    for f in files:
        src = os.path.join(WORKING_COPY_DIR, f)
        target = os.path.join(dest_dir, f)
        if os.path.isfile(src):
            shutil.move(src, target)
            moved.append(f)
    return jsonify({'moved': moved})


def notify(perc):
    for sid in connected_clients:
        socketio.emit('progress', {'percent': perc}, room=sid)
        print(perc)
        socketio.sleep(0)  # pozwala event loop obsłużyć inne zdarzenia (przełącznik kontekstu)


@socketio.on('connect')
def handle_connect():
    sid = request.sid
    connected_clients[sid] = {}  # Możesz przechowywać dodatkowe metadane, jeśli potrzeba
    print(f'Client connected: {sid}, total: {len(connected_clients)}')
    socketio.emit('progress', {'percent': 50})


@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    connected_clients.pop(sid, None)
    print(f'Client disconnected: {sid}, total: {len(connected_clients)}')


# @app.route('/refresh_face_tags')
# def refresh_face_tags():
#     # Uruchom proces aktualizacji w osobnym wątku, żeby nie blokować serwera
#     socketio.start_background_task(sq1w`)
#     return jsonify({"status": "started"}), 202


# klasyfikacja obrazków
device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)

# Kategorie, które chcemy rozpoznawać
categories = [
    "photo of person",
    "landscape photo",
    "document photo",
    "sheet music photo",
    "other"
]

# Preprocessujemy teksty do embeddingów
with torch.no_grad():
    text_inputs = clip.tokenize(categories).to(device)
    text_features = model.encode_text(text_inputs)
    text_features /= text_features.norm(dim=-1, keepdim=True)


def classify_image(img_path):
    image = preprocess(Image.open(img_path)).unsqueeze(0).to(device)
    with torch.no_grad():
        image_features = model.encode_image(image)
        image_features /= image_features.norm(dim=-1, keepdim=True)

        # Obliczamy podobieństwo cosine
        similarities = (100.0 * image_features @ text_features.T).softmax(dim=-1)
        probs = similarities.cpu().numpy()[0]

    # Wybieramy kategorię z najwyższym prawdopodobieństwem
    best_idx = probs.argmax()
    return categories[best_idx], float(probs[best_idx])


def classify_images_background_task():
    listdir = os.listdir(WORKING_COPY_DIR)
    total_steps = len(listdir)
    p = 0
    result = {}
    for img_path in listdir:
        if img_path.lower().endswith(('.jpg', '.jpeg', '.png')):
            full = os.path.join(WORKING_COPY_DIR, img_path)
            if not os.path.isfile(full):
                result[full] = {"error": "File not found"}
                continue
            category, score = classify_image(full)
            result[full] = {"category": category, "confidence": score}
        p += 1
        progress = int(p / total_steps * 100)
        notify(progress)
    # Zapisz surowe dane (nie jsonify!)
    save_image_tags(result, IMAGE_TAGS_PATH)
    print("Image classification finished.")


@app.route('/classify_images')
def classify_images():
    socketio.start_background_task(classify_images_background_task)
    return jsonify({"status": "started"}), 202


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5001, debug=True)
