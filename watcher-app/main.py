import os
import time
import shutil
import json
import zipfile
import tarfile
import logging

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
logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', level=logging.INFO, datefmt='%Y-%m-%d %H:%M:%S')


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


def copy_file_flat(src_path, dest_dir):
    """Kopiuje plik do dest_dir zachowując płaską strukturę, unikając nadpisania."""
    filename = os.path.basename(src_path)
    dest_path = unique_dest_path(dest_dir, filename)
    shutil.copy2(src_path, dest_path)
    logger.info(f"Skopiowano {src_path} -> {dest_path}")
    return dest_path


def move_file_flat(src_path, dest_dir):
    """Przenosi plik do dest_dir zachowując płaską strukturę, unikając nadpisania."""
    if is_stable(src_path):
        filename = os.path.basename(src_path)
        dest_path = unique_dest_path(dest_dir, filename)
        shutil.move(src_path, dest_path)
        logger.info(f"Przeniesiono {src_path} -> {dest_path}")
        file_size_cache.pop(src_path, None)  # remove from cache.
        return True
    return False


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
                logger.info(f"Rozpakowywanie archiwum: {archive_path}")
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
            logger.info(f"Pominięto: {full_path} (nie jest plikiem ani katalogiem lub jest w trakcie kopiowania)")


def process_additional_dir(input_dir):
    logger.info(f"Additional dir: {input_dir}")


def process_rules(rules):
    # Idziemy po plikach i przenosimy do katalogów wg reguł
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
            logger.info(f"- ext:  {ext}")
            if ext in extensions__:
                moved = move_file_flat(full_path, to__)
                if moved:
                    logger.info(f"- moved            : {os.path.basename(full_path)}")
                    files_moved += 1
        if files_moved > 0:
            logger.info(f"Przeniesiono {files_moved} plików z {from__} do {to__} wg reguł.")
        else:
            logger.debug(f"Przeniesiono {files_moved} plików z {from__} do {to__} wg reguł.")


def main():
    logging.basicConfig(filename='app.log', level=logging.INFO)
    # logging.getLogger().addHandler(logging.StreamHandler())
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
