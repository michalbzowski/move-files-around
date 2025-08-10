FROM python:3.11-slim

# Ustawienie katalogu roboczego
WORKDIR /app

# Instalacja podstawowych pakietów oraz Flask
RUN apt-get update && apt-get upgrade -y
RUN apt-get install -y git
RUN pip install --no-input --no-cache-dir flask pillow pdf2image poppler-utils numpy scikit-learn
RUN pip install --no-input --no-cache-dir git+https://github.com/ageitgey/face_recognition_models flask-socketio==5.3.4
RUN pip install --no-input --no-cache-dir python-socketio==5.8.0 python-engineio==4.4.1
RUN pip install --no-input --no-cache-dir eventlet
RUN pip install --upgrade pip
# Install torch and torchvision first (CPU-only example)
RUN pip install --no-cache-dir torch torchvision --extra-index-url https://download.pytorch.org/whl/cpu
# Clone and install CLIP without dependencies to skip redundant torch install
RUN mkdir /tmp/clip
RUN git clone https://github.com/openai/CLIP.git /tmp/clip
RUN pip install --timeout=1200 --no-cache-dir /tmp/clip



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
