# Je veux construire mon application à partir d'une image
# qui contient déjà Python 3.12
FROM python:3.12-slim

# Docker va utiliser /app comme dossier principal de ton projet.
WORKDIR /app

# Outils nécessaires(ensemble d'outils de compilation.) notamment pour installer mysqlclient.
RUN apt-get update \
    && apt-get install -y \
        build-essential \
        default-libmysqlclient-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copie requirements.txt dans /app/
COPY requirements.txt .

# Installation des dépendances Python.
RUN pip install --no-cache-dir -r requirements.txt

# Copie le projet Django dans /app/
COPY . .

# L'application utilise le port 8000.
EXPOSE 8000

# Lance Django.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]