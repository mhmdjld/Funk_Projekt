# Stage 1: Base build stage
FROM python:3.9-slim AS builder

# Erstelle das App-Verzeichnis
RUN mkdir /app

# Setze das Arbeitsverzeichnis
WORKDIR /app

# Installiere System-Abhängigkeiten (z.B. gcc und build-essential)
RUN apt-get update && apt-get install -y gcc build-essential

# Setze Umgebungsvariablen für Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Upgrade pip
RUN pip install --upgrade pip

# Kopiere die requirements.txt (sodass der Cache genutzt werden kann)
COPY requirements.txt /app/

# Installiere die Python-Abhängigkeiten
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Production stage
FROM python:3.9-slim

RUN useradd -m -r appuser && \
    mkdir /app && \
    chown -R appuser /app

COPY --from=builder /usr/local/lib/python3.9/site-packages/ /usr/local/lib/python3.9/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

WORKDIR /app

COPY --chown=appuser:appuser . .

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

USER appuser

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "weather_stations.wsgi:application"]

