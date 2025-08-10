FROM python:3.11-slim

# Ustawienie katalogu roboczego
WORKDIR /app

# Instalacja podstawowych pakietów oraz Flask
RUN apt-get update && apt-get upgrade -y
RUN apt-get install -y git
RUN pip install --no-input --no-cache-dir flask
RUN pip install --no-input --no-cache-dir pillow
RUN pip install --no-input --no-cache-dir pdf2image
RUN pip install --no-input --no-cache-dir poppler-utils
RUN pip install --no-input --no-cache-dir numpy
RUN pip install --no-input --no-cache-dir scikit-learn
RUN pip install --no-input --no-cache-dir git+https://github.com/ageitgey/face_recognition_models flask-socketio==5.3.4
RUN pip install --no-input --no-cache-dir python-socketio==5.8.0 python-engineio==4.4.1
RUN pip install --no-input --no-cache-dir eventlet
RUN git clone https://github.com/openai/CLIP.git /tmp/clip && \
    pip install --no-cache-dir /tmp/clip && \
    pip install --no-input --no-cache-dir torchvision



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
