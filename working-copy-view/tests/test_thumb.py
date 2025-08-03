import os
import tempfile
from thumb import serve_thumbnail, get_thumb_path

def test_image_thumbnail_generation(monkeypatch):
    from PIL import Image
    from flask import Flask

    app = Flask(__name__)

    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = os.path.join(tmpdir, "test.jpg")
        img = Image.new("RGB", (500, 500), (255, 0, 0))
        img.save(img_path, "JPEG")
        monkeypatch.setattr('thumb.WORKING_COPY_DIR', tmpdir)
        monkeypatch.setattr('thumb.THUMBNAILS_DIR', tmpdir)

        with app.test_request_context():
            resp = serve_thumbnail("100x100", "test.jpg")
            assert resp.status_code == 200
            # sprawdź czy miniatura się wygenerowała
            thumb_path = get_thumb_path("100x100", "test.jpg")
            assert os.path.exists(thumb_path)
