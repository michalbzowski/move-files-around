FROM python:3.11-slim

# Instalacja wymaganych pakietów (np. watchdog i unzip)
RUN pip install --no-cache-dir watchdog

WORKDIR /app

# Kopiujemy kod aplikacji
COPY . .

# Domyślne polecenie uruchamiające skrypt Pythona
CMD ["python", "main.py"]
