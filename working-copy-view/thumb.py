# thumb.py
import os
from PIL import Image
from flask import send_file, abort, current_app
from werkzeug.utils import secure_filename

WORKING_COPY_DIR = os.environ.get('WORKING_COPY_DIR', '../directories/test_dir/working_copy')
THUMBNAILS_DIR = os.path.join(os.getcwd(), 'thumbnails')


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
