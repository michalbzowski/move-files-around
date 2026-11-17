import os
import time
import shutil
import json
import zipfile
import tarfile
import logging
import hashlib
import urllib.request
from logging.handlers import TimedRotatingFileHandler

# Default values are needed when run locally.
# Then I do not need define them
# in IDE in run properties.
INPUT_DIR = os.getenv("INPUT_DIR", "../directories/test_dir/input")
PROCESSING_DIR = os.getenv("PROCESSING_DIR", "../directories/test_dir/processing")
PROCESSED_DIR = os.getenv("PROCESSED_DIR", "../directories/test_dir/processed")
UNPROCESSABLE_DIR = os.getenv("UNPROCESSABLE_DIR", "../directories/test_dir/unprocessable")
TMP_DIR = os.getenv("TMP_DIR", "../directories/test_dir/tmp")
WORKING_COPY_DIR = os.getenv("WORKING_COPY_DIR", "../directories/test_dir/working_copy")
BIN_DIR = os.getenv("BIN_DIR", "../directories/test_dir/bin")
ALL_MEDIA_DIR = os.getenv("ALL_MEDIA_DIR", "../directories/test_dir/all_media")
FILE_SLICE_SIZE = os.getenv("FILE_SLICE_SIZE", 1000)
CONFIG_FILE = os.getenv("CONFIG_FILE", "rules.json")
# --- Logging (fix: unbounded app.log in container /app → rotated /logs/app.log) ---
LOG_DIR = os.getenv("LOG_DIR", "./logs")
LOG_FILE = os.getenv("LOG_FILE", "")  # empty => LOG_DIR/app.log
LOG_RETENTION_WEEKS = int(os.getenv("LOG_RETENTION_WEEKS", "4"))   # 4 weekly backups ≈ 1 month
LOG_LEVEL_NAME = os.getenv("LOG_LEVEL", "INFO")
# Twardy budzet calkowitej zajetosci logow app.log* w LOG_DIR (domyślnie 1 GiB).
LOG_MAX_TOTAL_BYTES = int(os.getenv("LOG_MAX_TOTAL_BYTES", str(1024 ** 3)))

ALL_INPUT_DIRS = os.getenv("ADDITIONAL_DIRS", "../directories/test_dir/additional_01") + "," + INPUT_DIR

RULE_DIRS = {
    "INPUT_DIR": INPUT_DIR,
    "PROCESSING_DIR": PROCESSING_DIR,
    "PROCESSED_DIR": PROCESSED_DIR,
    "UNPROCESSABLE_DIR": UNPROCESSABLE_DIR,
    "TMP_DIR": TMP_DIR,
    "WORKING_COPY_DIR": WORKING_COPY_DIR,
    "BIN_DIR": BIN_DIR,
    "ALL_MEDIA_DIR": ALL_MEDIA_DIR,
    "ALL_MEDIA_PHOTOS_DIR": ALL_MEDIA_DIR + "/photos",
    "PP_IMPORT_DIR": ALL_MEDIA_DIR + "/incoming",
    "ALL_MEDIA_VIDEOS_DIR": ALL_MEDIA_DIR + "/videos",
    "ALL_MEDIA_MUSICS_DIR": ALL_MEDIA_DIR + "/musics",
    "ALL_MEDIA_VOICE_RECORDINGS_DIR": ALL_MEDIA_DIR + "/voice_recordings",
    "ALL_MEDIA_BOOKS_DIR": ALL_MEDIA_DIR + "/books",
    "ALL_MEDIA_FLAC_FILES_DIR": ALL_MEDIA_DIR + "/flacs",
    "ALL_MEDIA_ISO_FILES_DIR": ALL_MEDIA_DIR + "/isos",
    "ALL_MEDIA_MID_FILES_DIR": ALL_MEDIA_DIR + "/midis",
}

ARCHIVE_EXTENSIONS = ['zip', 'tar', 'tar.gz', 'tgz', 'tar.bz2', 'tbz2', 'tar.xz', 'txz', '7z', "rar"]
file_size_cache = {}


def _setup_logging():
    """Configure logging exactly once.

    - File: ${LOG_DIR}/app.log — TimedRotatingFileHandler, weekly (Monday),
      keep LOG_RETENTION_WEEKS backups (default 4 ≈ 1 month) → hard cap on size.
    - Stream: stdout, so `docker logs` still works; capped to INFO+ by default
      so DEBUG-only per-file noise from the file log does NOT flood /var/lib/docker.
    - Level: LOG_LEVEL env var (default INFO; DEBUG for tracing).
    """
    effective_log_file = LOG_FILE or os.path.join(LOG_DIR, "app.log")
    os.makedirs(os.path.dirname(effective_log_file) or ".", exist_ok=True)

    log_level = getattr(logging, LOG_LEVEL_NAME.upper(), logging.INFO)
    fmt = "%(asctime)s %(levelname)-8s %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    marker = "_moved_files_around_handler_marker"

    root = logging.getLogger()
    # Guard: do not stack handlers on repeated calls (e.g. re-import in tests).
    if any(getattr(h, marker, False) for h in root.handlers):
        return

    file_handler = TimedRotatingFileHandler(
        effective_log_file, when="W0", interval=1,
        backupCount=LOG_RETENTION_WEEKS, encoding="utf-8",
    )
    file_handler.suffix = "%Y-W%V"   # e.g. 2026-W34
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    setattr(file_handler, marker, True)

    stream_handler = logging.StreamHandler()
    # Never let DEBUG on the file handler leak DEBUG spam to stdout/container logs.
    stream_handler.setLevel(min(log_level, logging.INFO))
    stream_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    setattr(stream_handler, marker, True)

    root.setLevel(log_level)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)


_setup_logging()
logger = logging.getLogger(__name__)


def load_rules():
    logger.info(f"Ładuję rules.json")
    logger.info(os.getcwd())

    if not os.path.isfile(CONFIG_FILE):
        logger.info(f"Brak pliku z regułami: {CONFIG_FILE}, domyślne puste reguły")
        return {"extensions_to_move": []}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        rules = json.load(f)
    return rules


def is_archive(filename):
    filename_lower = filename.lower()
    for ext in ARCHIVE_EXTENSIONS:
        if filename_lower.endswith(ext):
            return True
    return False


def unique_dest_path(dest_dir, filename):
    """
    Jeśli plik o nazwie filename istnieje w dest_dir,
    dodajemy numer suffix, np. file(1).ext, file(2).ext itd.
    """
    base, ext = os.path.splitext(filename)
    counter = 1
    candidate = filename
    while os.path.exists(os.path.join(dest_dir, candidate)):
        candidate = f"{base}({counter}){ext}"
        counter += 1
    return os.path.join(dest_dir, candidate)


def _sha256_of(path, chunk_size=1024 * 1024):
    """Hash sha256 pliku w strumieniu (duze pliki wideo nie zjeda RAM-u)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def same_content_in(dest_dir, src_path):
    """Czy dest_dir juz zawiera plik o tym samym rozmiarze i sha256 co src_path?

    Najpierw tani filtr po rozmiarze (stat), hash tylko kandydatow.
    Skanuje caly katalog - chwytaja tez duplikaty po zmianie nazwy.
    """
    try:
        size = os.path.getsize(src_path)
    except OSError as e:
        logger.warning(f"Nie da sie odczytac rozmiaru {src_path}: {e}")
        return False
    for name in os.listdir(dest_dir):
        candidate = os.path.join(dest_dir, name)
        try:
            if not os.path.isfile(candidate) or os.path.getsize(candidate) != size:
                continue
            if _sha256_of(candidate) == _sha256_of(src_path):
                return True
        except OSError as e:
            logger.warning(f"Ignoruje {candidate}: {e}")
    return False


def enforce_log_budget():
    """Twardy limit zajetosci katalogu LOG_DIR (pliki app.log*).

    TimedRotatingFileHandler gwarantuje rotacje czasowa, ale bez limitu
    rozmiaru jeden bardzo aktywny tydzien urośnie ponad budzet. Tu:
    gdy suma przekracza LOG_MAX_TOTAL_BYTES (domyślnie 1 GiB), usuwamy
    najstarsze zapasy - zawsze zostaje aktualny app.log.
    """
    log_file = os.path.abspath(LOG_FILE or os.path.join(LOG_DIR, "app.log"))
    try:
        files = [os.path.join(LOG_DIR, n) for n in os.listdir(LOG_DIR)]
    except OSError as e:
        logger.warning(f"Ograniczenie logow: brak dostepu do {LOG_DIR}: {e}")
        return
    files = [f for f in files if os.path.isfile(f) and os.path.basename(f).startswith("app.log")]
    rotated = sorted(f for f in files if os.path.abspath(f) != log_file)
    total = sum(os.path.getsize(f) for f in files)
    guard = 0
    while total > LOG_MAX_TOTAL_BYTES and rotated and guard < 100:
        oldest = rotated.pop(0)  # suffix %Y-W%V: porzadek alfabetyczny == chronologiczny
        try:
            freed = os.path.getsize(oldest)
            os.remove(oldest)
        except OSError as e:
            logger.error(f"Ograniczenie logow: nie usunieto {oldest}: {e}")
            break
        total -= freed
        guard += 1
        logger.info(f"Ograniczenie logow: usunieto najstarszy odcinek {os.path.basename(oldest)} (budzet: {LOG_MAX_TOTAL_BYTES} B)")


def copy_file_flat(src_path, dest_dir):
    """Kopiuje plik do dest_dir zachowując płaską strukturę, unikając nadpisania."""
    filename = os.path.basename(src_path)
    dest_path = unique_dest_path(dest_dir, filename)
    shutil.copy2(src_path, dest_path)
    logger.debug(f"Skopiowano {src_path} -> {dest_path}")
    return dest_path


def move_file_flat(src_path, dest_dir):
    """Przenosi plik do dest_dir zachowując płaską strukturę, unikając nadpisania."""
    if not is_stable(src_path):
        return False
    filename = os.path.basename(src_path)
    if same_content_in(dest_dir, src_path):
        # Nie tworz kopii (1)/(2), gdy w dest juz jest ten sam plik:
        # nadmiarowa kopia trafia do BIN_DIR, oryginał w dest zostaje.
        bin_path = unique_dest_path(BIN_DIR, filename)
        shutil.move(src_path, bin_path)
        file_size_cache.pop(src_path, None)
        logger.info(f"Zduplikowany plik (ten sam sha256): '{filename}' juz jest w {dest_dir} -> nadmiarowa kopia trafia do BIN ({os.path.basename(bin_path)})")
        return False
    dest_path = unique_dest_path(dest_dir, filename)
    shutil.move(src_path, dest_path)
    logger.debug(f"Przeniesiono {src_path} -> {dest_path}")
    file_size_cache.pop(src_path, None)  # remove from cache.
    return True


def extract_archives_from_dir_to_flat_destination(archive_path, dest_dir):
    """Rozpakowuje archiwum do dest_dir w płaskiej strukturze."""
    extracted_files = []

    listdir = os.listdir(archive_path)
    for entry in listdir:
        full_path = os.path.join(archive_path, entry)
        if not is_stable(full_path):
            continue
        try:
            if not os.path.isdir(full_path):
                logger.debug(f"Rozpakowywanie archiwum: {archive_path}")
                if full_path.lower().endswith(".zip"):
                    with zipfile.ZipFile(full_path, 'r') as zf:
                        for member in zf.infolist():
                            if member.is_dir():
                                continue
                            filename = os.path.basename(member.filename)
                            if not filename:
                                continue
                            dest_path = unique_dest_path(dest_dir, filename)
                            with zf.open(member) as source, open(dest_path, "wb") as target:
                                shutil.copyfileobj(source, target)
                            extracted_files.append(dest_path)
                            logger.info(f"  Wyjęto plik {filename} -> {dest_path}")
                elif any(full_path.lower().endswith(ext) for ext in
                         ['.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2', '.tar.xz', '.txz']):
                    with tarfile.open(full_path, 'r:*') as tf:
                        for member in tf.getmembers():
                            if member.isdir():
                                continue
                            filename = os.path.basename(member.name)
                            if not filename:
                                continue
                            dest_path = unique_dest_path(dest_dir, filename)
                            with tf.extractfile(member) as source, open(dest_path, "wb") as target:
                                shutil.copyfileobj(source, target)
                            extracted_files.append(dest_path)
                            logger.info(f"  Wyjęto plik {filename} -> {dest_path}")

                else:
                    move_file_flat(full_path, UNPROCESSABLE_DIR)
                    logger.info(f"Nieobsługiwany format archiwum: {archive_path}")
            move_file_flat(full_path, PROCESSED_DIR)
        except Exception as e:
            move_file_flat(full_path, UNPROCESSABLE_DIR)
            logger.info(f"Błąd przy rozpakowywaniu {archive_path}: {e}")
    return extracted_files


def get_all_files_recursively(dir_path):
    for root, dirs, files in os.walk(dir_path):
        for f in files:
            yield os.path.join(root, f)


def remove_empty_dirs(path):
    # Przechodzimy po katalogach od najgłębszych (bottom-up)
    for root, dirs, files in os.walk(path, topdown=False):
        for d in dirs:
            dirpath = os.path.join(root, d)
            try:
                if not os.listdir(dirpath):  # katalog pusty
                    os.rmdir(dirpath)
                    logger.info(f"Usunięto pusty katalog: {dirpath}")
            except Exception as e:
                logger.info(f"Nie udało się usunąć katalogu {dirpath}: {e}")


def is_stable(full_path):
    if os.path.isfile(full_path):
        try:
            previous_size = file_size_cache.get(full_path, None)
            size = os.path.getsize(full_path)
            if previous_size != size:
                logger.info(f"File {os.path.basename(full_path)} size is unstable (prev: {previous_size} vs act: {size})")
                file_size_cache[full_path] = size
                return False
            else:
                return True
        except FileNotFoundError:
            # Plik nie istnieje
            logger.info(f"File {full_path} doesn't exists")
            return False
    else:
        logger.info(f"{full_path} is not a file")
        return False


def process_input_dir(input_dir):
    # 1. Znajdź nowe pliki i katalogi w INPUT_DIR
    # 2. Dla katalogów przenosimy ich zawartość plik po pliku do TMP_DIR do płaskiej strukturze
    # 3. Dla plików:
    #    - jeśli archiwum -> rozpakuj do TMP_DIR + przenieś archiwum do PROCESSED_DIR
    #    - jeśli zwykły plik -> skopiuj do TMP_DIR

    processed_archives = []  # do przeniesienia do processed (po rozpakowaniu)

    listdir = os.listdir(input_dir)
    for entry in listdir:
        full_path = os.path.join(input_dir, entry)
        if os.path.isdir(full_path):
            logger.info(f"Przetwarzanie katalogu: {full_path}")
            # Rekurencyjnie kopiuj pliki z podkatalogu do TMP_DIR
            process_input_dir(full_path)
            remove_empty_dirs(full_path)
        elif os.path.isfile(full_path):
            if is_archive(entry):
                # przenieś archiwum do innego katalogu - procesowanie w następnym kroku
                move_file_flat(full_path, PROCESSING_DIR)
            else:
                # zwykły plik - kopiuj do TMP_DIR
                move_file_flat(full_path, TMP_DIR)
        else:
            logger.debug(f"Pominięto: {full_path} (nie jest plikiem ani katalogiem lub jest w trakcie kopiowania)")


def process_additional_dir(input_dir):
    logger.info(f"Additional dir: {input_dir}")


def trigger_pp_index(photo_count):
    """Zapoczątkowuje indeks PhotoPrism (zweryfikowany 2026-11-16:
    POST /api/v1/session → access_token, następnie POST /api/v1/index z Bearer).
    Throttle przez plik stanowy; awaria PP nigdy nie psuje watchera."""
    base = os.getenv("PP_BASE_URL", "").rstrip("/")
    user = os.getenv("PP_ADMIN_USER", "")
    password = os.getenv("PP_ADMIN_PASS", "")
    if not base or not user:
        logger.debug(f"Trigger PP pominięty ({photo_count} foto, brak konfigu).")
        return
    state_file = "/tmp/last_pp_index"
    min_interval = int(os.getenv("PP_INDEX_MIN_INTERVAL", "1800"))
    try:
        with open(state_file) as fh:
            if time.time() - float(fh.read().strip() or 0) < min_interval:
                logger.info(f"Trigger PP pominięty ({photo_count} foto, za wcześnie).")
                return
    except Exception:
        pass
    try:
        req = urllib.request.Request(
            base + "/api/v1/session",
            data=json.dumps({"username": user, "password": password}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            token = json.load(resp).get("access_token")
        if not token:
            raise RuntimeError("brak access_token w odpowiedzi sesji")
        req2 = urllib.request.Request(
            base + "/api/v1/index",
            headers={"Authorization": "Bearer " + token},
            method="POST",
        )
        with urllib.request.urlopen(req2, timeout=30) as resp2:
            resp2.read()
        with open(state_file, "w") as fh:
            fh.write(str(time.time()))
        logger.info(f"PhotoPrism: indeks zapoczątkowany ({photo_count} nowych foto).")
    except Exception as e:
        logger.warning(f"Trigger PP nie działa (watcher trwa dalej): {e}")


def process_rules(rules):
    # Idziemy po plikach i przenosimy do katalogów wg reguł
    photo_moves = 0
    rule_set = rules.get("move")
    for rule in rule_set:
        logger.info(f"Rule: ")
        files_moved = 0
        from_ = rule["from"]
        from__ = RULE_DIRS[from_]
        to_ = rule["to"]
        to__ = RULE_DIRS[to_]
        extensions__ = rule["extensions"]
        logger.info(f"- from: {from__}")
        logger.info(f"- to:   {to__}")
        logger.info(f"- exts: {extensions__}")
        listdir = os.listdir(from__)
        logger.info(f"- all:  {len(listdir)}")
        for f in listdir:
            full_path = os.path.join(from__, f)
            if not os.path.isfile(full_path):
                continue
            ext = os.path.splitext(f)[1].lower().lstrip('.')  # usuń kropkę i zmień na małe litery
            logger.debug(f"- ext: {ext}")  # INFO = 62 mln linii dziennie przy backlogu tmp; debug w razie potrzeby
            if ext in extensions__:
                moved = move_file_flat(full_path, to__)
                if moved:
                    logger.info(f"- moved            : {os.path.basename(full_path)}")
                    files_moved += 1
                    if to_ == "ALL_MEDIA_PHOTOS_DIR":
                        photo_moves += 1
        if files_moved > 0:
            logger.info(f"Przeniesiono {files_moved} plików z {from__} do {to__} wg reguł.")
        else:
            logger.debug(f"Przeniesiono {files_moved} plików z {from__} do {to__} wg reguł.")

    if photo_moves > 0:
        # Foto ląduje w originals PhotoPrism — niech się samo zaindeksuje.
        trigger_pp_index(photo_moves)


def main():
    # Logging already configured at module import time (_setup_logging).
    # The old `logging.basicConfig(filename='app.log')` here re-pointed the
    # root logger to an unbounded ./app.log, discarding the rotating handler —
    # exactly the /var-filling bug. Removed on purpose: do NOT re-add it.
    logger.info('Started')
    poll_interval = int(os.getenv("INPUT_POLL_INTERVAL", "10"))
    logger.info(f"Start procesu z interwałem pollingu: {poll_interval} sekund")
    ensure_directories()
    rules = load_rules()

    while True:
        logger.info(f"Rozpoczynam kolejne sprawdzenie")
        try:
            for input_dir in ALL_INPUT_DIRS.split(","):
                process_input_dir(input_dir)
                remove_empty_dirs(input_dir)
            extract_archives_from_dir_to_flat_destination(PROCESSING_DIR, INPUT_DIR)

            process_rules(rules)
            enforce_log_budget()
        except Exception as e:
            logger.info(f"Błąd w procesie: {e}")

        logger.info(f"Czekam {poll_interval} sekund")
        time.sleep(poll_interval)


def ensure_directories():
    logger.info(f"Tworzę katalogi, jeśli nie istnieją")
    for key, value in RULE_DIRS.items():
        os.makedirs(value, exist_ok=True)
    # additional dirs are not created because they are additional


if __name__ == "__main__":
    main()
