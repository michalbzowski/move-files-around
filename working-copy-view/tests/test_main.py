import os
import tempfile
from main import app, format_bytes


def test_format_bytes():
    assert format_bytes(100) == "100 B"
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(1024 * 1024) == "1.00 MB"


def test_index_returns_200(monkeypatch):
    client = app.test_client()

    # Zapewnij tymczasowy katalog z plikami
    with tempfile.TemporaryDirectory() as tmpdir:
        # Utwórz próbny plik
        test_file = os.path.join(tmpdir, "plik.txt")
        with open(test_file, "w") as f:
            f.write("Hello")
        monkeypatch.setattr('main.WORKING_COPY_DIR', tmpdir)
        response = client.get('/')
        assert response.status_code == 200
        assert b'Pliki' in response.data


def test_index_filtering(monkeypatch):
    client = app.test_client()
    with tempfile.TemporaryDirectory() as tmpdir:
        for name in ["a.txt", "b.jpg", "noext"]:
            with open(os.path.join(tmpdir, name), "w") as f:
                f.write("x")
        monkeypatch.setattr('main.WORKING_COPY_DIR', tmpdir)
        # Filtr po rozszerzeniu txt
        resp = client.get('/?ext=txt')
        assert b'a.txt' in resp.data
        assert b'b.jpg' not in resp.data

        # Filtr plików bez rozszerzenia
        resp = client.get('/?ext=no_ext')
        assert b'noext' in resp.data


def test_file_serving(monkeypatch):
    client = app.test_client()
    with tempfile.TemporaryDirectory() as tmpdir:
        fname = "a.pdf"
        path = os.path.join(tmpdir, fname)
        with open(path, "wb") as f:
            f.write(b"%PDF-")
        monkeypatch.setattr('main.WORKING_COPY_DIR', tmpdir)
        resp = client.get(f'/files/{fname}')
        assert resp.status_code == 200
        assert resp.data.startswith(b"%PDF-")
