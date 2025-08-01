import os
import time
import shutil
import json
import zipfile
import tarfile
import logging

INPUT_DIR = os.getenv("INPUT_DIR", "../directories/test_dir/input")
PROCESSING_DIR = os.getenv("PROCESSING_DIR", "../directories/test_dir/processing")
PROCESSED_DIR = os.getenv("PROCESSED_DIR", "../directories/test_dir/processed")
UNPROCESSABLE_DIR = os.getenv("UNPROCESSABLE_DIR", "../directories/test_dir/unprocessable")
TMP_DIR = os.getenv("TMP_DIR", "../directories/test_dir/tmp")
WORKING_COPY_DIR = os.getenv("WORKING_COPY_DIR", "../directories/test_dir/working_copy")
BIN_DIR = os.getenv("BIN_DIR", "../directories/test_dir/bin")
ALL_MEDIA_DIR = os.getenv("ALL_MEDIA_DIR", "../directories/test_dir/all_media")
CONFIG_FILE = os.getenv("CONFIG_FILE", "rules.json")

ARCHIVE_EXTENSIONS = ['zip', 'tar', 'tar.gz', 'tgz', 'tar.bz2', 'tbz2', 'tar.xz', 'txz']

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


def copy_file_flat(src_path, dest_dir):
    """Kopiuje plik do dest_dir zachowując płaską strukturę, unikając nadpisania."""
    filename = os.path.basename(src_path)
    dest_path = unique_dest_path(dest_dir, filename)
    shutil.copy2(src_path, dest_path)
    logger.info(f"Skopiowano {src_path} -> {dest_path}")
    return dest_path


def move_file_flat(src_path, dest_dir):
    """Przenosi plik do dest_dir zachowując płaską strukturę, unikając nadpisania."""
    filename = os.path.basename(src_path)
    dest_path = unique_dest_path(dest_dir, filename)
    shutil.move(src_path, dest_path)
    logger.info(f"Przeniesiono {src_path} -> {dest_path}")
    return dest_path


def extract_archives_from_dir_to_flat_destination(archive_path, dest_dir):
    """Rozpakowuje archiwum do dest_dir w płaskiej strukturze."""
    extracted_files = []

    listdir = os.listdir(archive_path)
    for entry in listdir:
        full_path = os.path.join(archive_path, entry)
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
                #przenieś archiwum do innego katalogu - procesowanie w następnym kroku
                move_file_flat(full_path, PROCESSING_DIR)
            else:
                # zwykły plik - kopiuj do TMP_DIR
                move_file_flat(full_path, TMP_DIR)
        else:
            logger.info(f"Pominięto: {full_path} (nie jest plikiem ani katalogiem)")

    # Przenieś rozpakowane archiwa do PROCESSED_DIR
    # for archive_path in processed_archives:
    #     move_file_flat(archive_path, PROCESSED_DIR)


def process_tmp_dir(rules):
    # Idziemy po plikach w TMP_DIR i przenosimy do WorkingCopy wg reguł (rozszerzenia)
    ext_set = set(rules.get("extensions_to_move", []))
    files_moved = 0
    for f in os.listdir(TMP_DIR):
        full_path = os.path.join(TMP_DIR, f)
        if not os.path.isfile(full_path):
            continue
        ext = os.path.splitext(f)[1].lower().lstrip('.')  # usuń kropkę i zmień na małe litery
        if ext in ext_set:
            move_file_flat(full_path, WORKING_COPY_DIR)
            files_moved += 1
    logger.info(f"Przeniesiono {files_moved} plików z tmp do WorkingCopy wg reguł.")


def main():


    logging.basicConfig(filename='app.log', level=logging.INFO)
    logging.getLogger().addHandler(logging.StreamHandler())
    logger.info('Started')
    poll_interval = int(os.getenv("INPUT_POLL_INTERVAL", "10"))
    logger.info(f"Start procesu z interwałem pollingu: {poll_interval} sekund")
    ensure_directories()
    rules = load_rules()

    while True:
        logger.info(f"Rozpoczynam kolejne sprawdzenie")
        try:
            process_input_dir(INPUT_DIR)
            remove_empty_dirs(INPUT_DIR)
            extract_archives_from_dir_to_flat_destination(PROCESSING_DIR, INPUT_DIR)

            process_tmp_dir(rules)
        except Exception as e:
            logger.info(f"Błąd w procesie: {e}")

        logger.info(f"Czekam {poll_interval} sekund")
        time.sleep(poll_interval)



def ensure_directories():

    logger.info(f"Tworzę katalogi, jeśli nie istnieją")
    logger.info(os.getcwd())
    logger.info("KOTEK")
    logger.info(INPUT_DIR)
    logger.info("PIESEK")
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(PROCESSING_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(UNPROCESSABLE_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    os.makedirs(WORKING_COPY_DIR, exist_ok=True)
    os.makedirs(BIN_DIR, exist_ok=True)
    os.makedirs(ALL_MEDIA_DIR, exist_ok=True)


if __name__ == "__main__":
    main()
