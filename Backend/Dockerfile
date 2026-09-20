FROM python:3.12-slim

# Evita archivos .pyc y hace los logs inmediatos
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instala dependencias primero (mejor caché de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Buenas prácticas de seguridad: correr sin root
RUN useradd -m appuser
USER appuser

EXPOSE 8000
CMD ["sh", "entrypoint.sh"]
