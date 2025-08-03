import os
from math import ceil

from flask import Flask, render_template, send_from_directory, request, jsonify, send_file, abort
import mimetypes
from datetime import datetime
from thumb import serve_thumbnail
import shutil

app = Flask(__name__)
WORKING_COPY_DIR = os.getenv("WORKING_COPY_DIR", "../directories/test_dir/working_copy")
BIN_DIR = os.getenv("BIN_DIR", "../directories/test_dir/bin")
ALL_MEDIA_DIR = os.getenv("ALL_MEDIA_DIR", "../directories/test_dir/all_media")


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


@app.route('/thumb/<size>/<filename>')
def thumbnail(size, filename):
    return serve_thumbnail(size, filename)


@app.route('/')
def index():
    name = request.args.get('name', '').lower()
    filter_ext = [e.lower() for e in request.args.getlist('ext') if e]

    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))

    all_files = []
    extensions_set = set()
    has_no_ext = False

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

            stat = os.stat(full)

            all_files.append({
                'name': f,
                'size': stat.st_size,
                'date': datetime.fromtimestamp(stat.st_mtime),
                'type': get_file_type(f)
            })

    total_files = len(all_files)
    total_pages = ceil(total_files / per_page)

    # Wycinanie „strony” z listy plików
    start = (page - 1) * per_page
    end = start + per_page
    files = all_files[start:end]

    # Przekaż do template: files, page, total_pages, per_page i inne dane

    extensions_list = sorted(extensions_set)
    # Przekaż rozszerzenia jako lista i flagę czy są pliki bez rozszerzenia
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
                           per_page=per_page)


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
