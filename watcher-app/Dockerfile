FROM python:3.11-slim

# Instalacja wymaganych pakietów (np. watchdog i unzip)
RUN pip install --no-cache-dir watchdog

WORKDIR /app

# Pre-create the log directory inside the image so TimedRotatingFileHandler
# has a target even before the bind-mount attaches (docker-compose mounts
# ./logs here at runtime).  No chown needed — container runs as root by default.
RUN mkdir -p /logs && chmod 0775 /logs

# Kopiujemy kod aplikacji
COPY . .

# Domyślne polecenie uruchamiające skrypt Pythona
CMD ["python", "main.py"]
