FROM python:3.11-slim

WORKDIR /app

# Dépendances système nécessaires pour la cryptographie et SSL
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libssl-dev \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Installer les dépendances Python d'abord (cache Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copier le code source
COPY . .

# Créer les répertoires nécessaires
RUN mkdir -p users_data

# Port exposé (Back4App utilise 8080)
ENV PORT=8080
EXPOSE 8080

# Lancer directement bot.py
CMD ["python", "-u", "bot.py"]
