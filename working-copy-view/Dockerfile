FROM python:3.11-slim

# Ustawienie katalogu roboczego
WORKDIR /app

# Instalacja podstawowych pakietów oraz Flask
RUN pip install --no-cache-dir flask

# Kopiujemy cały kod aplikacji (app.py, templates, static itp.)
COPY . .

# Ustawiamy zmienną środowiskową, aby Flask uruchomił app.py w trybie produkcyjnym na 0.0.0.0:5000
ENV FLASK_APP=main.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_ENV=production

# Otwieramy port 5000
EXPOSE 5001

# Domyślna komenda uruchamiająca serwer Flask
CMD ["flask", "run"]
