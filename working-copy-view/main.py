import os
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
    ext = request.args.get('ext', '').lower()
    name = request.args.get('name', '').lower()
    files = []
    for f in os.listdir(WORKING_COPY_DIR):
        full = os.path.join(WORKING_COPY_DIR, f)
        if os.path.isfile(full):
            if ext and not f.lower().endswith(f'.{ext}'):
                continue
            if name and name not in f.lower():
                continue
            stat = os.stat(full)
            files.append({
                'name': f,
                'size': stat.st_size,
                'date': datetime.fromtimestamp(stat.st_mtime),
                'type': get_file_type(f)
            })
    files_sorted = sorted(files, key=lambda x: x['name'].lower())
    return render_template('index.html',
                           files=files_sorted,
                           filter_name=name,
                           filter_ext=ext,
                           total_files=len(files_sorted),
                           total_size=sum(f['size'] for f in files_sorted))


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
