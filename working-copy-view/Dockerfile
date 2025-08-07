FROM python:3.11-slim

# Ustawienie katalogu roboczego
WORKDIR /app

# Instalacja podstawowych pakietów oraz Flask
RUN pip install --no-cache-dir flask pillow pdf2image poppler-utils face_recognition numpy scikit-learn git+https://github.com/ageitgey/face_recognition_models flask-socketio==5.3.4  python-socketio==5.8.0 python-engineio==4.4.1 eventlet git+https://github.com/openai/CLIP.git torchvision


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
